import io
import os
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch
import shutil
from linux_performance_doctor import collectors


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def proc_stat(pid, name, ticks, start, rss):
    fields = ["1"] * 22
    fields[11], fields[12] = str(ticks), "0"
    fields[19], fields[20], fields[21] = str(start), "4096", str(rss)
    return f"{pid} ({name}) R " + " ".join(fields) + "\n"


class CollectorTests(unittest.TestCase):
    def test_cpu_counters_and_process_names_with_spaces(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            shutil.copytree(Path(__file__).parent / 'fixtures/proc', root, dirs_exist_ok=True)
            self.assertEqual(collectors.cpu_counters(root), (960, 810))
            proc = collectors.process_counters(root)[123]
            self.assertEqual(proc['name'], 'worker ) x')
            self.assertEqual(proc['ticks'], 30)
            self.assertEqual(proc['starttime'], 1234)
            self.assertEqual(proc['rss_bytes'], 5 * os.sysconf('SC_PAGE_SIZE'))

    def test_cpu_and_process_are_deltas_over_two_samples_and_rss_is_reported(self):
        before = {7: {'pid': 7, 'name': 'hot', 'ticks': 100, 'starttime': 10, 'rss_bytes': 2000}}
        after = {7: {'pid': 7, 'name': 'hot', 'ticks': 150, 'starttime': 10, 'rss_bytes': 3000},
                 8: {'pid': 8, 'name': 'big', 'ticks': 0, 'starttime': 11, 'rss_bytes': 9000}}
        meta = {'status': 'ok', 'visible': 2, 'readable': 2, 'unreadable': 0, 'limitations': []}
        snapshots = iter([(before, meta), (after, meta)])
        counters = iter([(1000, 200), (1300, 250)])
        with patch.object(collectors, 'cpu_counters', side_effect=lambda _: next(counters)), \
             patch.object(collectors, '_process_snapshot', side_effect=lambda _: next(snapshots)), \
             patch.object(collectors.time, 'sleep'), patch.object(collectors.time, 'monotonic', side_effect=[1, 3]):
            result = collectors.collect_cpu_and_processes(Path('/fixture'), interval=2, clock_ticks=100)
        self.assertEqual(result['cpu_percent'], 83.3)
        self.assertEqual(result['processes_by_cpu'][0]['cpu_percent_one_core'], 25.0)
        self.assertEqual(result['processes_by_cpu'][0]['rss_bytes'], 3000)
        self.assertEqual(result['processes_by_rss'][0]['pid'], 8)
        self.assertEqual(result['processes_by_rss'][0]['rss_bytes'], 9000)

    def test_pid_reuse_does_not_inherit_cpu_delta(self):
        before = {7: {'pid': 7, 'name': 'old', 'ticks': 100, 'starttime': 10, 'rss_bytes': 2000}}
        after = {7: {'pid': 7, 'name': 'new', 'ticks': 500, 'starttime': 99, 'rss_bytes': 3000}}
        meta = {'status': 'ok', 'visible': 1, 'readable': 1, 'unreadable': 0, 'limitations': []}
        snapshots = iter([(before, meta), (after, meta)])
        with patch.object(collectors, 'cpu_counters', side_effect=[(100, 20), (200, 30)]), \
             patch.object(collectors, '_process_snapshot', side_effect=lambda _: next(snapshots)), \
             patch.object(collectors.time, 'sleep'), patch.object(collectors.time, 'monotonic', side_effect=[1, 2]):
            result = collectors.collect_cpu_and_processes(Path('/fixture'), interval=1, clock_ticks=100)
        self.assertEqual(result['processes_by_cpu'], [])
        self.assertEqual(result['processes_by_rss'][0]['name'], 'new')

    def test_process_visibility_unavailable_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            result, status = collectors._process_snapshot(Path(d) / 'missing')
        self.assertEqual(status['status'], 'unavailable')
        self.assertTrue(status['limitations'])

    def test_memory_missing_fields_stay_missing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write(root/'meminfo', 'MemTotal: 1000 kB\nMemAvailable: 200 kB\n')
            write(root/'vmstat', 'pswpin 12\n')
            got = collectors.collect_memory(root)
            self.assertEqual(got['memory_used_percent'], 80.0)
            self.assertIsNone(got['swap_total_bytes'])
            self.assertIsNone(got['swap_pages_out'])

    def test_filesystem_empty_and_unreadable_mounts_are_not_ok(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write(root/'self/mounts', '')
            self.assertEqual(collectors.collect_filesystems(root)['status'], 'unavailable')
            root2 = Path(d) / 'without-mount-file'
            self.assertEqual(collectors.collect_filesystems(root2)['status'], 'unavailable')

    def test_filesystem_with_unavailable_counters_is_partial(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            mount = Path(d) / 'mnt'
            mount.mkdir()
            write(root/'self/mounts', f'/dev/test {mount} ext4 rw 0 0\n')
            stats = SimpleNamespace(f_blocks=0, f_frsize=4096, f_bavail=0, f_files=0, f_favail=0)
            with patch.object(collectors.os, 'statvfs', return_value=stats):
                result = collectors.collect_filesystems(root)
        self.assertEqual(result['status'], 'partial')
        self.assertIsNone(result['filesystems'][0]['used_percent'])
        self.assertTrue(result['limitations'])

    def test_io_missing_counters_are_not_ok(self):
        with tempfile.TemporaryDirectory() as d, patch.object(collectors.time, 'sleep'):
            result = collectors.collect_io(Path(d), interval=0.1)
        self.assertEqual(result['status'], 'unavailable')
        self.assertIsNone(result['devices'])
        self.assertTrue(result['limitations'])

    def test_sensor_values_are_bounded_and_missing_is_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual(collectors.collect_sensors(root)['status'], 'unavailable')
            write(root/'class/thermal/thermal_zone0/temp', '95000')
            write(root/'class/thermal/thermal_zone0/type', 'cpu-thermal')
            self.assertEqual(collectors.collect_sensors(root)['sensors'][0]['temperature_c'], 95.0)

    def test_systemd_is_service_only_has_bounded_output_and_fixed_environment(self):
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b'bad.service loaded failed failed broken\n')
        os.close(write_fd)
        with os.fdopen(read_fd, 'rb') as output:
            fake = type('Process', (), {'stdout': output, 'wait': lambda self, timeout=None: 0, 'kill': lambda self: None})()
            with patch.object(collectors.shutil, 'which', return_value='/usr/bin/systemctl'), \
                 patch.object(collectors.subprocess, 'Popen', return_value=fake) as popen:
                result = collectors.collect_failed_services()
        self.assertEqual(result['services'][0]['unit'], 'bad.service')
        args, kwargs = popen.call_args
        self.assertIn('--type=service', args[0])
        self.assertNotIn('shell', kwargs)
        self.assertEqual(kwargs['env']['LANG'], 'C')
        self.assertEqual(kwargs['env']['LC_ALL'], 'C')

    def test_systemd_output_limit_is_applied(self):
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b'a' * 50)
        os.close(write_fd)
        with os.fdopen(read_fd, 'rb') as output:
            fake = type('Process', (), {'stdout': output, 'wait': lambda self, timeout=None: -9, 'kill': lambda self: None})()
            with patch.object(collectors.shutil, 'which', return_value='/usr/bin/systemctl'), \
                 patch.object(collectors.subprocess, 'Popen', return_value=fake):
                result = collectors.collect_failed_services(max_output_bytes=10)
        self.assertEqual(result['status'], 'partial')
        self.assertLessEqual(len(str(result)), 1000)

    def test_systemd_unavailable_when_not_installed(self):
        with patch.object(collectors.shutil, 'which', return_value=None):
            self.assertEqual(collectors.collect_failed_services()['status'], 'unavailable')

    def test_process_collection_never_reads_cmdline_or_environ(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write(root/'88'/'stat', proc_stat(88, 'safe', 20, 5, 2))
            with patch.object(collectors, 'read_text', wraps=collectors.read_text) as read:
                collectors.process_counters(root)
            paths = [str(c.args[0]) for c in read.call_args_list]
            self.assertTrue(all(not p.endswith(('cmdline', 'environ')) for p in paths))

if __name__ == '__main__':
    unittest.main()
