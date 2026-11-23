import io
import unittest
from dataclasses import FrozenInstanceError

from Cloud_test.iot_eval.messages import Command, Hello, InferenceResult, Telemetry
from Cloud_test.iot_eval.protocol import Message, read_message, write_message


HASH = "a" * 64
HELLO = {
    "phase": "E06_PHYSICAL",
    "model": "vit",
    "firmware_sha256": HASH,
    "artifact_hashes": {"weights.bin": "b" * 64},
    "board_ip": "192.168.1.20",
    "tcp_port": 5000,
}
TELEMETRY = {
    "timestamp_ticks": 9,
    "power_uW": 123,
    "temperature_mC": 40000,
    "completed_frames": 2,
    "sensor_valid": True,
}
COMMAND = {"name": "start", "arguments": {"frames": 3, "labels": ["a", "b"]}}
INFERENCE = {
    "predicted_class": 1,
    "mismatch_count": 0,
    "total_ticks": 100,
    "pl_ticks": 50,
    "mm2s_ticks": 20,
    "s2mm_ticks": 30,
}


class TypedMessageTests(unittest.TestCase):
    def test_each_type_round_trips_through_wire(self):
        for cls, kind, fields in (
            (Hello, "hello", HELLO),
            (Telemetry, "telemetry", TELEMETRY),
            (Command, "command", COMMAND),
            (InferenceResult, "inference_result", INFERENCE),
        ):
            with self.subTest(kind=kind):
                value = cls(**fields)
                message = value.to_message(19)
                self.assertEqual(message, Message(kind, 19, fields))
                stream = io.BytesIO()
                write_message(stream, message)
                stream.seek(0)
                self.assertEqual(cls.from_message(read_message(stream)), value)
                with self.assertRaises(FrozenInstanceError):
                    value.__setattr__(next(iter(fields)), None)

    def test_hello_rejects_invalid_phase_hash_ip_and_port(self):
        changes = (
            {"phase": "UNKNOWN"},
            {"phase": []},
            {"firmware_sha256": "A" * 64},
            {"firmware_sha256": "a" * 63},
            {"artifact_hashes": {}},
            {"artifact_hashes": {"": HASH}},
            {"artifact_hashes": {"weights.bin": "z" * 64}},
            {"board_ip": "256.1.1.1"},
            {"board_ip": "::1"},
            {"tcp_port": 0},
            {"tcp_port": 65536},
        )
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    Hello(**(HELLO | change))

    def test_hello_accepts_all_phases_and_port_bounds(self):
        for phase in ("HOST_LOOPBACK", "E06_PHYSICAL", "PLANT_PHYSICAL"):
            for port in (1, 65535):
                with self.subTest(phase=phase, port=port):
                    self.assertEqual(Hello(**(HELLO | {"phase": phase, "tcp_port": port})).tcp_port, port)

    def test_telemetry_rejects_invalid_counters_and_sensor_combinations(self):
        changes = (
            {"timestamp_ticks": -1},
            {"completed_frames": -1},
            {"power_uW": -1},
            {"temperature_mC": -1},
            {"power_uW": None},
            {"temperature_mC": None},
            {"sensor_valid": 1},
        )
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    Telemetry(**(TELEMETRY | change))
        self.assertEqual(Telemetry(**(TELEMETRY | {
            "power_uW": None, "temperature_mC": None, "sensor_valid": False,
        })).power_uW, None)

    def test_command_rejects_empty_name_and_non_json_arguments(self):
        for changes in ({"name": ""}, {"arguments": []},
                        {"arguments": {1: "bad key"}},
                        {"arguments": {"value": object()}},
                        {"arguments": {"value": float("nan")}}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    Command(**(COMMAND | changes))

    def test_inference_rejects_negative_counters(self):
        for field in INFERENCE:
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    InferenceResult(**(INFERENCE | {field: -1}))

    def test_from_message_rejects_wrong_kind_missing_extra_and_payload(self):
        for cls, kind, fields in (
            (Hello, "hello", HELLO),
            (Telemetry, "telemetry", TELEMETRY),
            (Command, "command", COMMAND),
            (InferenceResult, "inference_result", INFERENCE),
        ):
            with self.subTest(kind=kind):
                for message in (
                    Message("ack", 1, fields),
                    Message(kind, 1, {key: value for key, value in fields.items()
                                      if key != next(iter(fields))}),
                    Message(kind, 1, fields | {"unknown": 1}),
                    Message(kind, 1, fields, b"unexpected"),
                ):
                    with self.assertRaises(ValueError):
                        cls.from_message(message)

    def test_from_message_rejects_invalid_field_values(self):
        for cls, kind, fields, change in (
            (Hello, "hello", HELLO, {"phase": "invalid"}),
            (Telemetry, "telemetry", TELEMETRY, {"completed_frames": -1}),
            (Command, "command", COMMAND, {"arguments": []}),
            (InferenceResult, "inference_result", INFERENCE, {"total_ticks": -1}),
        ):
            with self.subTest(kind=kind):
                with self.assertRaises(ValueError):
                    cls.from_message(Message(kind, 1, fields | change))


if __name__ == "__main__":
    unittest.main()
