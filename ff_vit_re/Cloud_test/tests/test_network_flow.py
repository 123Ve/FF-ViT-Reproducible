import json
from pathlib import Path
import tempfile
import threading
import unittest

from Cloud_test.iot_eval.client import send_cloud_frame, send_edge_result
from Cloud_test.iot_eval.server import CloudServer


class NetworkFlowTests(unittest.TestCase):
    def test_cloud_and_edge_messages_complete_over_real_tcp(self):
        with tempfile.TemporaryDirectory() as directory:
            event_log = Path(directory) / "events.jsonl"
            server = CloudServer(("127.0.0.1", 0), event_log=event_log, num_classes=38)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                cloud = send_cloud_frame(
                    host, port, request_id=1, name="leaf.rgb", rgb=b"\x01\x02\x03"
                )
                edge = send_edge_result(
                    host,
                    port,
                    request_id=2,
                    class_id=7,
                    confidence_q15=30000,
                    inference_us=3370,
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

            self.assertEqual(cloud.response.kind, "cloud_result")
            self.assertEqual(cloud.response.metadata["class_id"], 6)
            self.assertEqual(cloud.payload_bytes, 3)
            self.assertEqual(edge.response.kind, "ack")
            self.assertEqual(edge.response.metadata["accepted_class_id"], 7)
            self.assertEqual(edge.payload_bytes, 0)

            events = [json.loads(line) for line in event_log.read_text().splitlines()]
            self.assertEqual([event["mode"] for event in events], ["cloud", "edge"])
            self.assertEqual([event["payload_bytes"] for event in events], [3, 0])


if __name__ == "__main__":
    unittest.main()
