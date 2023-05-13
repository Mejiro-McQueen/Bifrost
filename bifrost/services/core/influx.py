from bifrost.common.service import Service
from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception
from ait.core import log
import ait
import traceback
from bifrost.services.downlink.alarms import Alarm_State
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
import urllib3
import json
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Influx(Service):
    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.start()

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        self.pass_id = await self.config_request_pass_id()
        self.sv_name = await self.config_request_sv_name()
        await super().reconfigure(topic, message, reply)
        self.setup_connection()

    @with_loud_exception
    def setup_connection(self):
        try:
            self.client = InfluxDBClient(url=self.host_url,
                                         token=self.api_token,
                                         org=self.org,
                                         verify_ssl=False)
            #query_api = client.query_api()
            self.buckets_api = self.client.buckets_api()
            self.buckets_api.create_bucket(bucket_name=self.sv_name,
                                           org=self.org)
        except Exception as e:
            if e.response.status == 422:
                pass
            else:
                log.error(e)
                log.error(traceback.print_exc())
                raise e

    @with_loud_coroutine_exception
    async def write_dataframe(self, topic, data, reply):
        def process_df(task):
            if task.df is not None:
                try:
                    df = task.df
                    self.dbconn.pandas_client.write_points(df,
                                                           task.measurement,
                                                           tag_columns=[c.name for c in Alarm_State])
                    log.debug(f"Processed {task}")
                    task.result = True
                    self.publish('Bifrost.Messages.Info.File_Manager.Task_Done', task)
                    return
                except Exception as e:
                    log.error(e)
            return
        process_df(data)

    @with_loud_coroutine_exception
    async def write_command_metadata(self, topic, cmd_struct, reply):
        print(cmd_struct)
        cmd_struct.pop('processors')
        cmd_struct.pop('payload_bytes')
        fields = cmd_struct
        t = fields['start_time_gps']
        #t.format = 'iso'
        #t = t.datetime.isoformat("T") + "Z"
        d = [{'time': t,
              'measurement': 'BIFROST_COMMAND_HISTORY',
              'fields': fields,
              'tags': {'sv_name': self.sv_name,
                       'pass_id': str(self.pass_id),
                       'user': 'Future'},
              }]
        with self.client.write_api(write_options=SYNCHRONOUS) as f:
            f.write(bucket=self.sv_name, record=d)

    @with_loud_coroutine_exception
    async def write_telemetry(self, topic, data, reply):
        # Consider using Jetstream instead
        #log.info(f'{json.dumps(data)=}')
        try:
            packet_metadata = data
            packet_name = packet_metadata['packet_name']
            decoded = packet_metadata['decoded_packet']
            alarms = packet_metadata['field_alarms']
            gps_timestamp = packet_metadata['packet_time']
            pass_id = packet_metadata['pass_id']
            alarm_tags = {c.name: None for c in Alarm_State}
            fields = {}
            tags = {}
            alarm_tags = {c.name: None for c in Alarm_State}
            for (field_name, value) in decoded.items():
                val = value
                c = alarms[field_name]['state']
                if alarm_tags[c]:
                    alarm_tags[c] += f", {field_name}"
                else:
                    alarm_tags[c] = f"{field_name}"

                fields[field_name] = val

            # TODO: Python 3.9 -> tags = tags | alarm_tags
            tags = {**alarm_tags, **tags}
            tags['pass_id'] = pass_id

            #gps_timestamp.format = 'iso'
            #time = gps_timestamp.datetime.isoformat("T") + "Z"
            data = {"time": gps_timestamp,
                    "measurement": packet_name,
                    "tags": tags,
                    "fields": fields}

            with self.client.write_api(write_options=SYNCHRONOUS) as f:
                f.write(bucket=self.sv_name, record=data)

        except Exception as e:
            log.error(f"Data archival failed with error: {e}")
            log.error(traceback.print_exc())
