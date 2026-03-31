import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import zmq
import json

class ZmqBridge(Node):
    def __init__(self):
        super().__init__('zmq_bridge')
        self.pub = self.create_publisher(String, 'chatter', 10)
        
        # ZMQ subscriber
        context = zmq.Context()
        self.socket = context.socket(zmq.SUB)
        self.socket.connect("tcp://localhost:5555")
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
        
        # Poll ZMQ in ROS2 timer
        self.timer = self.create_timer(0.01, self.poll_zmq)
    
    def poll_zmq(self):
        try:
            data = self.socket.recv_json(flags=zmq.NOBLOCK)
            msg = String()
            msg.data = json.dumps(data)
            self.pub.publish(msg)
            self.get_logger().info(f'Bridged: {data}')
        except zmq.Again:
            pass  # No data available

def main():
    rclpy.init()
    node = ZmqBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
