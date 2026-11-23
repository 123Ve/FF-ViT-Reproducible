import io
import struct
import unittest

from Cloud_test.iot_eval.protocol import Message, ProtocolError, read_message, write_message


class ProtocolTests(unittest.TestCase):
    def test_binary_payload_round_trip(self):
        stream = io.BytesIO()
        message = Message(
            kind="cloud_frame",
            request_id=17,
            metadata={"name": "leaf.rgb", "width": 2, "height": 1},
            payload=b"\x00\x7f\xff\x10\x20\x30",
        )

        wire_bytes = write_message(stream, message)
        stream.seek(0)

        self.assertEqual(read_message(stream), message)
        self.assertEqual(wire_bytes, len(stream.getvalue()))

    def test_rejects_bad_magic(self):
        stream = io.BytesIO(b"BAD!" + b"\x00" * 20)

        with self.assertRaisesRegex(ProtocolError, "magic"):
            read_message(stream)

    def test_rejects_nonzero_reserved_header_bytes(self):
        for reserved in (0x0001, 0x0100):
            with self.subTest(reserved=reserved):
                header = struct.pack("!4sBBHIII", b"FVIT", 1, 5, reserved, 7, 2, 0)
                with self.assertRaisesRegex(ProtocolError, "reserved"):
                    read_message(io.BytesIO(header + b"{}"))

    def test_one_byte_reads_reconstruct_header_metadata_and_payload(self):
        class FragmentedStream(io.BytesIO):
            def read(self, size=-1):
                return super().read(1 if size < 0 else min(size, 1))

        original = Message("telemetry", 23, {"sensor_valid": False}, b"\x00\xff")
        encoded = io.BytesIO()
        write_message(encoded, original)

        self.assertEqual(read_message(FragmentedStream(encoded.getvalue())), original)

    def test_oversize_lengths_are_rejected_before_body_reads(self):
        class HeaderOnlyStream(io.BytesIO):
            def read(self, size=-1):
                if self.tell() >= 20:
                    self.fail_body_read = True
                    raise AssertionError("body read attempted")
                return super().read(size)

        header = struct.Struct("!4sBBHIII")
        for metadata_length, payload_length in ((65537, 0), (0, 4194305)):
            with self.subTest(metadata_length=metadata_length, payload_length=payload_length):
                stream = HeaderOnlyStream(header.pack(b"FVIT", 1, 1, 0, 0,
                                                     metadata_length, payload_length))
                stream.fail_body_read = False
                with self.assertRaisesRegex(ProtocolError, "size limit"):
                    read_message(stream)
                self.assertFalse(stream.fail_body_read)

    def test_new_message_kinds_have_stable_distinct_wire_codes(self):
        for kind, code in (("hello", 5), ("telemetry", 6),
                           ("command", 7), ("inference_result", 8)):
            with self.subTest(kind=kind):
                stream = io.BytesIO()
                write_message(stream, Message(kind, 1, {}))
                self.assertEqual(stream.getvalue()[5], code)
                stream.seek(0)
                self.assertEqual(read_message(stream).kind, kind)


if __name__ == "__main__":
    unittest.main()
