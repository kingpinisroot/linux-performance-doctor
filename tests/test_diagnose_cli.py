import json
import unittest
from unittest.mock import patch
from linux_performance_doctor.diagnose import diagnose
from linux_performance_doctor import cli


def sample():
    return {'modules': {name: {'status': 'ok', 'limitations': []} for name in ('cpu', 'processes', 'memory_swap', 'filesystems', 'io', 'sensors', 'systemd_services')},
            'cpu': {'cpu_percent': 91}, 'memory': {'memory_used_percent': 96, 'swap_pages_in': 2, 'swap_pages_out': 0},
            'filesystems': {'status': 'ok', 'filesystems': [{'mountpoint': '/', 'used_percent': 91, 'inodes_used_percent': 90}]},
            'sensors': {'status': 'ok', 'sensors': [{'name': 'cpu', 'temperature_c': 90}]},
            'services': {'status': 'ok', 'services': [{'unit': 'bad.service'}]}}


class DiagnoseTests(unittest.TestCase):
    def test_conservative_thresholds_emit_evidence_and_action_fields(self):
        findings = diagnose(sample())
        self.assertEqual(len(findings), 7)
        self.assertTrue(all({'metric', 'severity', 'threshold', 'evidence', 'explanation', 'suggestion', 'impact', 'uncertainty'} <= set(x) for x in findings))
        self.assertEqual(findings[0]['severity'], 'warning')

    def test_every_non_ok_module_becomes_unknown_not_ok(self):
        data = sample()
        data['modules']['filesystems'] = {'status': 'unavailable', 'limitations': ['mount table empty']}
        data['modules']['processes'] = {'status': 'partial', 'limitations': ['some entries unreadable']}
        data['filesystems'] = {'status': 'unavailable', 'filesystems': []}
        findings = diagnose(data)
        unknown_metrics = {f['metric'] for f in findings if f['severity'] == 'unknown'}
        self.assertTrue({'filesystems', 'processes'} <= unknown_metrics)

    def test_missing_data_is_unknown_not_ok(self):
        data = {'modules': {'cpu': {'status': 'unavailable', 'limitations': ['no counters']},
                            'io': {'status': 'unavailable', 'limitations': ['diskstats unreadable']},
                            'sensors': {'status': 'unavailable', 'limitations': ['no sensors']}},
                'cpu': {'cpu_percent': None}, 'memory': {}, 'filesystems': {'status': 'unavailable', 'filesystems': []},
                'sensors': {'status': 'unavailable', 'sensors': []}, 'services': {'status': 'unavailable', 'services': None}}
        findings = diagnose(data)
        self.assertTrue({'cpu', 'io', 'sensors'} <= {f['metric'] for f in findings if f['severity'] == 'unknown'})

    def test_first_sample_swap_counters_are_always_unknown_without_baseline(self):
        cpu = {'cpu_percent': 10, 'interval_seconds': .1, 'processes_by_cpu': [], 'processes_by_rss': [],
               'process_count_sampled': 1, 'process_status': 'ok', 'process_limitations': []}
        memory = {'memory_total_bytes': 1000, 'memory_available_bytes': 500, 'memory_used_percent': 50,
                  'swap_total_bytes': 1000, 'swap_free_bytes': 500, 'swap_used_percent': 50,
                  'swap_pages_in': 10000, 'swap_pages_out': 20000}
        with patch.object(cli.platform, 'system', return_value='Linux'), \
             patch.object(cli, 'read_text', return_value=None), \
             patch.object(cli, 'collect_memory', side_effect=[memory.copy(), memory.copy()]), \
             patch.object(cli, 'collect_cpu_and_processes', return_value=cpu), \
             patch.object(cli, 'collect_filesystems', return_value={'status': 'ok', 'filesystems': [], 'limitations': []}), \
             patch.object(cli, 'collect_io', return_value={'status': 'ok', 'devices': [], 'limitations': [], 'interval_seconds': .1}), \
             patch.object(cli, 'collect_sensors', return_value={'status': 'unavailable', 'sensors': [], 'limitations': ['none']}), \
             patch.object(cli, 'collect_failed_services', return_value={'status': 'unavailable', 'services': None, 'limitations': ['missing']}):
            result = cli.scan(.1)
        self.assertIsNone(result['memory']['swap_pages_in'])
        self.assertIsNone(result['memory']['swap_pages_out'])
        self.assertEqual(result['modules']['memory_swap']['status'], 'partial')

    def test_cli_supports_lpdoctor_scan_json(self):
        payload = {'cpu': {'cpu_percent': 1, 'interval_seconds': .1, 'processes_by_cpu': [], 'processes_by_rss': []},
                   'memory': {}, 'filesystems': {'filesystems': []}, 'io': {'devices': [], 'interval_seconds': .1},
                   'sensors': {'sensors': []}, 'services': {'services': []}, 'modules': {}, 'findings': [], 'generated_at': 'now'}
        with patch.object(cli, 'scan', return_value=payload), patch('sys.stdout') as out:
            self.assertEqual(cli.main(['scan', '--json']), 0)
            emitted = ''.join(str(c.args[0]) for c in out.write.call_args_list)
            self.assertEqual(json.loads(emitted)['cpu']['cpu_percent'], 1)
        with patch.object(cli.platform, 'system', return_value='Darwin'):
            with self.assertRaises(RuntimeError):
                cli.scan()

    def test_interval_validation(self):
        with patch('sys.stderr'):
            with self.assertRaises(SystemExit):
                cli.main(['scan', '--interval', '0'])

if __name__ == '__main__':
    unittest.main()
