import sys
import tornado.ioloop
import tornado.web
import tornado.httpserver
import tornado.httputil
import tornado.gen
from tornado import escape
import json
import pickle
import numpy as np
import json
from grpc.beta import implementations
import tensorflow as tf
import predict_pb2
import prediction_service_pb2

from hystrix import Command
import asyncio

grpc_host = "127.0.0.1"
grpc_port = 9000
model_name = "linear"
model_version = -1 # Latest version 
request_timeout = 5.0 # 5 seconds

class TensorflowServingGrpcCommand(Command, *args, **kwargs):
  def __init__(self, inputs):
    super().__init__(*args, **kwargs)
    self.inputs = inputs

  def run(self):
    # TODO:  pass on the actual inputs
    return self.do_post(self.request.body) 

  def do_post(self, inputs):
    # Convert json input to tensor
    input_str = input_binary.decode('utf-8')
    input_json = json.loads(input_str)
    inputs_np = np.asarray([input_str['x_observed']])
    print(inputs_np)
    inputs_tensor_proto = tf.contrib.util.make_tensor_proto(inputs_np,
                                                            dtype=tf.float32)
    # Build the PredictRequest from inputs
    request = predict_pb2.PredictRequest()
    request.model_spec.name = model_name
    if model_version > 0:
      request.model_spec.version.value = model_version
    request.inputs['x_observed'].CopyFrom(inputs_tensor_proto)

    # Create gRPC client and request
    grpc_port = int(sys.argv[2])
    channel = implementations.insecure_channel(grpc_host, grpc_port)
    stub = prediction_service_pb2.beta_create_PredictionService_stub(channel)

    # Send request
    result = stub.Predict(request, request_timeout)
    print(result)

    # Convert PredictResult into np array
    result_np = tf.contrib.util.make_ndarray(result.outputs['y_pred'])
    print(result_np)

    # Convert np array into json
    result_json = json.dumps(result_np.tolist()))
    print(result_json)

    return result_json

  def fallback(self):
    return 'fallback!'

class MainHandler(tornado.web.RequestHandler):
  @tornado.gen.coroutine
  def post(self):
    self.set_header("Content-Type", "application/json")

    command = self.build_command()

    do_post_result = yield self.build_future(command)   

    # Convert PredictResponse into json
    self.write(do_post_result)

  def build_command(self):
    command = TensorflowServingGrpcCommand()
    command.name = 'TensorflowServingGrpcCommand'
    command.group_name = 'TensorflowServingGrpcCommandGroup'
    return command

  def build_future(self, command):
    future = command.observe()
    future.add_done_callback(future.result)
    return future

if __name__ == "__main__":
  app = tornado.web.Application([
      (r"/v1/", MainHandler),
  ])
  listen_port = int(sys.argv[1])
  app.listen(listen_port)

  print("*****************************************************")
  print("Tornado-based http_grpc_proxy listening on port %s" % listen_port)
  print("*****************************************************")
  tornado.ioloop.IOLoop.current().start()
