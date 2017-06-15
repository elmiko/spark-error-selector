"""spark-error-selector

This app will look for keywords in the messages from a kafka topic,
and then take those messages and send them to another topic.
"""
import argparse

import kafka
import pyspark
from pyspark import streaming
from pyspark.streaming import kafka as kstreaming


class FilterStreamProcessor():
    """A class to filter Kafka stream data

    This class wraps the Spark and Kafka specific logic for creating a
    DStream and applying processing functions to the RDDs contained
    therein.

    If any message contains a word from the FILTER_LIST, those messages
    will be copied to the output topic.
    """
    FILTER_LIST = (
        'ERROR',
        'Error',
        'error',
        'WARN',
        'warn',
        'failed',
        'failure',
    )

    def __init__(self, input_topic, output_topic, servers, duration):
        """Create a new StreamProcessor

        Keyword arguments:
        input_topic -- Kafka topic to read messages from
        output_topic -- Kafka topic to write message to
        servers -- A list of Kafka brokers
        duration -- The window duration to sample the Kafka stream in
                    seconds
        """
        self.input_topic = input_topic
        self.output_topic = output_topic
        self.servers = servers
        self.spark_context = pyspark.SparkContext(
            appName='spark-kafka-skeleton')
        self.streaming_context = streaming.StreamingContext(
            self.spark_context, duration)
        self.kafka_stream = kstreaming.KafkaUtils.createDirectStream(
            self.streaming_context,
            [self.input_topic],
            {'bootstrap.servers': self.servers,
             'auto.offset.reset': 'smallest'})

    def configure_processing(self):
        """Configure the processing pipeline

        This function contains all the stream processing
        configuration that will affect how each RDD is processed.
        It will be called before the stream listener is started.
        """
        def send_filtered(rdd):
            """A function to publish an RDD to a Kafka topic"""
            producer = kafka.KafkaProducer(bootstrap_servers=self.servers)
            for r in rdd.collect():
                try:
                    record = r.encode('ascii', 'backslashreplace')
                    producer.send(self.output_topic, record)
                except Exception as e:
                    print('Error sending collected RDD')
                    print('Original exception: {}'.format(e))
            producer.flush()

        messages = self.kafka_stream.map(lambda m: m[1])
        #totalcount = messages.count()
        filtermessages = messages.filter(
            lambda r: any(word in r for word in FilterStreamProcessor.FILTER_LIST))
        #filtercount = filtermessages.count()
        filtermessages.foreachRDD(send_filtered)

    def start_and_await_termination(self):
        """Start the stream processor

        This function will start the Spark-based stream processor,
        it will run until `stop` is called or an exception is
        thrown.
        """
        self.configure_processing()
        self.streaming_context.start()
        self.streaming_context.awaitTermination()

    def stop(self):
        """Stop the stream processor"""
        self.streaming_context.stop()


def main():
    """The main function

    This will process the command line arguments and launch the main
    Spark/Kafka monitor class.
    """
    parser = argparse.ArgumentParser(
        description='process data with Spark, using Kafka as the transport')
    parser.add_argument('--in', dest='input_topic',
        help='the kafka topic to read data from')
    parser.add_argument('--out', dest='output_topic',
        help='the kafka topic to publish data to')
    parser.add_argument('--servers', help='the kafka brokers')
    args = parser.parse_args()

    processor = FilterStreamProcessor(
        input_topic = args.input_topic,
        output_topic = args.output_topic,
        servers = args.servers,
        duration = 3)

    processor.start_and_await_termination()


if __name__ == '__main__':
    main()

