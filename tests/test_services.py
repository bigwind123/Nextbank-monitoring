import base64
import json
import secrets
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from monitoring.events import event, now, validate
from monitoring.ldap_auth import decode, authenticate
from monitoring.fleet_monitor import fetch_agents, transition
from monitoring.worker import DeliveryStore, deliver, ticket
from scripts.platform import init, ROOT


class EventTests(unittest.TestCase):
    def setUp(self):
        self.payload = event("CPU", "test-host", now(), {"Param1": "0.75"})

    def test_stable_replay_identity_and_conversion(self):
        self.assertEqual(self.payload["id"], event("CPU", "test-host", self.payload["timestamp"], {"Param1": "0.75"})["id"])
        result = ticket(self.payload, "operator")
        self.assertEqual(result["class"], "Incident")
        self.assertIn("75.000000%", json.loads(result["fields"]["description"])["CPU usage pct"])

    def test_replay_delivered_once(self):
        store = DeliveryStore(":memory:")
        sender = Mock()
        self.assertTrue(deliver(self.payload, store, sender, "operator"))
        self.assertFalse(deliver(self.payload, store, sender, "operator"))
        sender.assert_called_once()

    def test_failed_send_is_retryable(self):
        store = DeliveryStore(":memory:")
        sender = Mock(side_effect=TimeoutError)
        with self.assertRaises(TimeoutError):
            deliver(self.payload, store, sender, "operator")
        self.assertFalse(store.contains(self.payload["id"]))

    def test_invalid_event_rejected(self):
        invalid = {**self.payload, "timestamp": "invalid"}
        with self.assertRaises(ValueError):
            validate(invalid)

    def test_unknown_strategy_rejected(self):
        with self.assertRaises(ValueError):
            ticket({**self.payload, "kind": "unsupported"}, "operator")


class AuthTests(unittest.TestCase):
    def test_no_empty_password_or_malformed_header(self):
        for header in (None, "Bearer value", "Basic !", "Basic " + base64.b64encode(b"user:").decode()):
            with self.assertRaises((ValueError, UnicodeError)):
                decode(header)

    def test_password_can_contain_colons(self):
        value = secrets.token_hex(8) + ":" + secrets.token_hex(8)
        self.assertEqual(decode("Basic " + base64.b64encode(("user:" + value).encode()).decode()), ("user", value))

    def test_ldap_requires_tls(self):
        with self.assertRaises(ValueError):
            authenticate("user", secrets.token_hex(8), {"base": "invalid"}, "")


class FleetTests(unittest.TestCase):
    def test_pagination_collects_all_agents(self):
        import monitoring.fleet_monitor as module
        from unittest.mock import patch
        pages = [{"items": [{"id": "one"}], "total": 2}, {"items": [{"id": "two"}], "total": 2}]
        with patch.object(module, "request", side_effect=pages):
            self.assertEqual(len(fetch_agents(Mock(), "")), 2)

    def test_only_failure_state_transition_emits_event(self):
        agent = {"id": "agent", "status": "offline"}
        self.assertIsNotNone(transition(agent, "online"))
        self.assertIsNone(transition(agent, "offline"))
        self.assertIsNone(transition({**agent, "status": "online"}, "offline"))


class DeploymentTests(unittest.TestCase):
    def test_runtime_keeps_secrets_outside_source_and_preserves_them_on_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = Path(folder)
            cfg = init(runtime)
            password = (runtime / "secrets" / "reader-password").read_text()
            init(runtime)
            self.assertEqual(password, (runtime / "secrets" / "reader-password").read_text())
            self.assertNotIn(password, (ROOT / "compose.yaml").read_text())
            self.assertEqual(len(list((runtime / "rules").glob("*.yaml"))), 6)
            self.assertNotEqual(cfg["es"], cfg["kibana"])

    def test_reject_runtime_inside_repository(self):
        with self.assertRaises(ValueError):
            init(ROOT / ".runtime")


if __name__ == "__main__":
    unittest.main()
