import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import launcher


@unittest.skipUnless(shutil.which('git'), 'Git is required for launcher update tests')
class LauncherTests(unittest.TestCase):
    def run_git(self, root, *args):
        return subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                              text=True, check=True).stdout.strip()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.remote = self.base / 'origin.git'
        self.remote.mkdir()
        self.run_git(self.remote, 'init', '--bare', '--initial-branch=main')
        self.seed = self.base / 'seed'
        self.seed.mkdir()
        self.run_git(self.seed, 'init', '--initial-branch=main')
        self.run_git(self.seed, 'config', 'user.name', 'Test Fixture')
        self.run_git(self.seed, 'config', 'user.email', 'fixture@example.invalid')
        (self.seed / 'fixture.txt').write_text('initial\n')
        self.run_git(self.seed, 'add', 'fixture.txt')
        self.run_git(self.seed, 'commit', '-m', 'Initial fixture')
        self.run_git(self.seed, 'remote', 'add', 'origin', str(self.remote))
        self.run_git(self.seed, 'push', 'origin', 'main')
        self.checkout = self.base / 'checkout'
        self.run_git(self.base, 'clone', str(self.remote), str(self.checkout))
        self.trusted = patch('launcher.REMOTE', str(self.remote))
        self.trusted.start()

    def tearDown(self):
        self.trusted.stop()
        self.temporary.cleanup()

    def update(self):
        (self.seed / 'fixture.txt').write_text('approved update\n')
        self.run_git(self.seed, 'commit', '-am', 'Update fixture')
        self.run_git(self.seed, 'push', 'origin', 'main')

    def test_update_is_reviewed_and_applied_only_after_yes(self):
        self.update()
        answers = iter(['r', 'y'])
        output = []
        launcher.prepare(self.checkout, confirm=lambda _: next(answers), output=output.append)
        self.assertEqual(self.run_git(self.checkout, 'rev-parse', 'HEAD'), self.run_git(self.seed, 'rev-parse', 'HEAD'))
        self.assertTrue(any('+approved update' in item for item in output))

    def test_default_declines_without_changing_worktree(self):
        self.update()
        original = self.run_git(self.checkout, 'rev-parse', 'HEAD')
        launcher.prepare(self.checkout, confirm=lambda _: '', output=lambda _: None)
        self.assertEqual(self.run_git(self.checkout, 'rev-parse', 'HEAD'), original)
        self.assertEqual((self.checkout / 'fixture.txt').read_text(), 'initial\n')

    def test_dirty_worktree_and_unexpected_remote_are_rejected(self):
        (self.checkout / 'fixture.txt').write_text('local work\n')
        with self.assertRaisesRegex(launcher.LauncherError, 'Local changes'):
            launcher.prepare(self.checkout)
        self.run_git(self.checkout, 'restore', 'fixture.txt')
        self.run_git(self.checkout, 'remote', 'set-url', 'origin', 'https://example.invalid/untrusted.git')
        with self.assertRaisesRegex(launcher.LauncherError, 'Origin does not match'):
            launcher.prepare(self.checkout)

    def test_diverged_history_is_not_reset(self):
        self.update()
        self.run_git(self.checkout, 'config', 'user.name', 'Test Fixture')
        self.run_git(self.checkout, 'config', 'user.email', 'fixture@example.invalid')
        (self.checkout / 'local.txt').write_text('preserve this\n')
        self.run_git(self.checkout, 'add', 'local.txt')
        self.run_git(self.checkout, 'commit', '-m', 'Local commit')
        with self.assertRaisesRegex(launcher.LauncherError, 'ahead or diverged'):
            launcher.prepare(self.checkout)
        self.assertEqual((self.checkout / 'local.txt').read_text(), 'preserve this\n')

    def test_edits_during_review_are_not_overwritten(self):
        self.update()
        def edit(_):
            (self.checkout / 'fixture.txt').write_text('edited while reviewing\n')
            return 'y'
        with self.assertRaisesRegex(launcher.LauncherError, 'Local changes'):
            launcher.prepare(self.checkout, confirm=edit, output=lambda _: None)
        self.assertEqual((self.checkout / 'fixture.txt').read_text(), 'edited while reviewing\n')

    def test_offline_mode_does_not_fetch_or_prompt(self):
        with patch('launcher.git', wraps=launcher.git) as calls:
            launcher.prepare(self.checkout, offline=True, confirm=lambda _: self.fail('Unexpected prompt'), output=lambda _: None)
        self.assertFalse(any('fetch' in call.args for call in calls.call_args_list))


class SourceLayoutTests(unittest.TestCase):
    def test_connector_resolves_collector_scripts_from_git_checkout(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('source_connector_layout', root / 'connector/connector.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.ROOT, root)
        self.assertTrue((module.ROOT / 'scripts/Invoke-HealthCheck.ps1').is_file())
