import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packaging'))
import signing
import apple_ci


class SigningTests(unittest.TestCase):
    def test_release_cannot_fall_back_when_credentials_are_missing(self):
        for platform in ('win32', 'darwin'):
            with self.subTest(platform=platform), self.assertRaises(ValueError):
                signing.configuration(platform, {})
        with self.assertRaises(ValueError):
            signing.configuration('darwin', {'MACOS_SIGNING_IDENTITY': '-', 'MACOS_NOTARY_PROFILE': 'profile'})

    def test_provider_uses_an_argument_array_and_one_file_placeholder(self):
        for command in ('"signer {file}"', '[]', '["signer"]', '["signer", "{file}", "{file}"]'):
            with self.subTest(command=command), self.assertRaises(ValueError):
                signing.configuration('win32', {'WINDOWS_SIGN_COMMAND_JSON': command})
        config = signing.configuration('win32', {'WINDOWS_SIGN_COMMAND_JSON': '["provider", "sign", "{file}"]'})
        with tempfile.TemporaryDirectory() as folder, patch('signing.private_run') as run, patch('signing.verify_windows'):
            target = Path(folder) / 'app with spaces.exe'
            target.write_bytes(b'MZ-test')
            signing.sign_windows(target, config)
            self.assertEqual(run.call_args.args[0], ['provider', 'sign', str(target.resolve())])

    def test_provider_failures_do_not_expose_credentials(self):
        with patch('signing.subprocess.run', return_value=subprocess.CompletedProcess([], 1, b'secret output', b'private-key')):
            with self.assertRaises(RuntimeError) as caught:
                signing.private_run(['provider', '--token', 'super-secret-token'])
        self.assertNotIn('super-secret-token', str(caught.exception))
        self.assertNotIn('private-key', str(caught.exception))

    def test_project_certificate_does_not_resign_upstream_libraries(self):
        with tempfile.TemporaryDirectory() as folder, patch('signing.sign_windows') as sign:
            root = Path(folder)
            (root / 'OriginExtract.exe').write_bytes(b'MZ-project')
            dependency = root / 'Qt6Core.dll'
            dependency.write_bytes(b'MZ-upstream')
            signing.sign_windows_tree(root, signing.Signing('win32'))
            sign.assert_called_once()
            self.assertEqual(sign.call_args.args[0], root / 'OriginExtract.exe')
            self.assertEqual(dependency.read_bytes(), b'MZ-upstream')

    def test_notarization_rejection_never_staples_or_claims_acceptance(self):
        config = signing.Signing('darwin', notary_profile='profile')
        for status in ('Invalid', 'In Progress'):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as folder:
                report = Path(folder) / 'result.json'
                result = subprocess.CompletedProcess([], 0, json.dumps(dict(status=status, id='test-id')).encode(), b'')
                with patch('signing.private_run', return_value=result) as run:
                    with self.assertRaisesRegex(RuntimeError, 'did not accept'):
                        signing.notarize('app.zip', config, report, staple_target='app.app')
                    self.assertEqual(run.call_count, 1)
                    self.assertEqual(json.loads(report.read_text())['status'], status)

    def test_successful_zip_notarization_staples_the_app(self):
        config = signing.Signing('darwin', notary_profile='profile', keychain='/temp/ci.keychain-db')
        result = subprocess.CompletedProcess([], 0, b'{"status":"Accepted","id":"test-id"}', b'')
        with tempfile.TemporaryDirectory() as folder, patch('signing.private_run', return_value=result) as run:
            signing.notarize('app.zip', config, Path(folder) / 'result.json', staple_target='app.app')
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn('--keychain', commands[0])
        self.assertEqual(commands[1], ['xcrun', 'stapler', 'staple', 'app.app'])
        self.assertEqual(commands[2], ['xcrun', 'stapler', 'validate', 'app.app'])

    def test_missing_apple_secrets_do_not_create_a_keychain(self):
        with patch.dict('apple_ci.os.environ', {}, clear=True), patch('apple_ci.private_run') as run:
            with self.assertRaisesRegex(RuntimeError, 'Missing GitHub signing secrets'):
                apple_ci.setup()
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
