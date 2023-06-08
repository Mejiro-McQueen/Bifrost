from ait.core import log
from pathlib import Path
import tarfile
import bz2
from abc import ABC, abstractmethod
from tqdm import tqdm
import re
import importlib
import os
from urllib import parse
import pickle
from bifrost.common.service import Service
import asyncio
from bifrost.common.deep_dictionary_get import deep_get

class Task_Message(ABC):
    @classmethod
    def name(cls):
        return cls.__name__

    def __init__(self, ID, filepath):
        self.ID = ID
        self.result = None  # Result is usually published overpubsub
        self.name = self.name()
        self.filepath = Path(filepath)
        self.final = False  # Task is finalized. Do not execute, do not apply transformations, do not track.
        self.nofork = False  # Taskmanager will not fork to service this task

    def __repr__(self):
        return str(self.__dict__)

    @abstractmethod
    def execute(self):
        pass

    @abstractmethod
    def marshall(self):
        return self.__dict__.copy()

    @abstractmethod
    def unmarshall(d):
        res = Task_Message(d['ID'],
                           d['filepath'])
        res.result = d['result']
        res.name = d['name']
        res.final = d['final']
        res.nofork = d['nofork']
        return res


class Tasks():
    
    class File_Reassembly(Task_Message):
        """ This task is run automatically with ID = downlink ID"""
        def __init__(self, filepath, ground_tag, file_size=0,
                     file_reassembler=None, sv_fpath=None, config={}):
            Task_Message.__init__(self, ground_tag, filepath)
            self.ground_tag = ground_tag
            self.md5_file = ""
            self.file_reassembler = file_reassembler
            self.file_size = file_size
            self.sv_fpath = sv_fpath
            self.config = config

        def marshall(self, subset=False):
            d = self.__dict__.copy()
            d['sv_fpath'] = str(d['sv_fpath'])
            d['filepath'] = str(d['filepath'])
            if subset:
                d.pop('file_reassembler', None)
                d.pop('config', None)
                return d
            d['file_reassembler'] = pickle.dumps(d['file_reassembler'])
            return d

        @staticmethod
        def unmarshall(d):
            # TODO: Consider dataclass to avoid unpacking dict explicitly?
            d['file_reassembler'] = pickle.loads(d['file_reassembler'])
            o = Tasks.File_Reassembly(filepath=d['filepath'],
                                      ground_tag=d['ground_tag'],
                                      file_size=d['file_size'],
                                      file_reassembler=d['file_reassembler'],
                                      sv_fpath=d['sv_fpath'],
                                      config=d['config'])
            return o
            
        def execute(self):
            self.sv_name = deep_get(self.config, 'instance.space_vehicle.name')
            self.pass_id = deep_get(self.config, 'global.mission.pass_id')
            self.known_scid = deep_get(self.config, 'instance.space_vehicle.ccsds_downlink_scid', 0)
            self.file_reassembler(self.filepath, self.known_scid, self)
            os.sync()

    class S3_File_Upload(Task_Message):
        """
        Request FileManager to upload local path to S3 bucket.
        Task ID -1 denotes an internal task
        """
        
        # Use binary to specify object put instead of file put
        def __init__(self, ID, bucket, filepath, s3_path, s3_region, ground_tag=-1, binary=None, config=None):
            Task_Message.__init__(self, ID, filepath)
            self.bucket = bucket
            self.s3_path = s3_path
            self.ground_tag = ground_tag
            self.s3_region = s3_region
            self.metadata = None
            self.canonical_path = None
            self.file_size = os.path.getsize(filepath)
            assert config
            pass_id = deep_get(config, 'global.mission.pass_id')
            self.tags = {'pass_id': pass_id,
                         'sv_name': deep_get(config, 'instance.space_vehicle.name'),
                         'ground_tag': ground_tag,
                         }
            self.binary = binary

        def marshall(self):
            d = self.__dict__.copy()
            d['filepath'] = str(d['filepath'])
            return d

        @staticmethod
        def unmarshall(d):
            assert False, 'Not implemented.'

        def canonical_s3_url(self):
            if not self.result:  # S3 upload returns none when successful, contains an exception otherwise
                self.canonical_path = f"https://{self.bucket}.s3-{self.s3_region}.amazonaws.com/{self.s3_path}"
                self.metadata = {'s3_url': self.canonical_path,
                                 's3_region': self.s3_region,
                                 's3_bucket': self.bucket,
                                 's3_key': str(self.s3_path),
                                 's3_tags': str(self.tags)}

        def get_mime_type(self):
            ext = Path(self.filepath).suffix
            if ext in ['.log', '.cl']:
                res = 'text/plain'
            elif ext in ['.json', '.ndjson']:
                res = 'application/json'
            else:
                res = 'binary/octet-stream'
            return res
        
        def execute(self, s3_resource):
            try:
                if not self.binary:
                    with tqdm(total=self.file_size, unit='bytes',
                              unit_scale=True, desc=f"Task {self.ID} -> S3 Upload => {self.s3_path}",
                              colour='YELLOW') as pbar:
                    
                        response = s3_resource.Bucket(self.bucket).upload_file(str(self.filepath),
                                                                               self.s3_path,
                                                                               Callback=lambda b: pbar.update(b),
                                                                               ExtraArgs={"Tagging": parse.urlencode(self.tags),
                                                                                          'ContentType': self.get_mime_type()})
                else:
                    object = s3_resource.Object(self.bucket, self.s3_path)
                    response = object.put(Body=self.binary,
                                          #Callback=lambda b: pbar.update(b),
                                          Tagging=parse.urlencode(self.tags),
                                          ContentType=self.get_mime_type())
                        
                if response and not self.binary:
                    self.result = response
                    log.error(self.result)
            except Exception as e:
                log.error(e)
                self.result = str(e)
                return
            self.canonical_s3_url()
            #log.info(f"Task ID {self.ID} -> {self.filepath} uploaded to {self.canonical_path}")

    class CSV_to_Influx(Task_Message):
        def __init__(self, ID, filepath, postprocessor):
            Task_Message.__init__(self, ID, filepath)
            self.postprocessor = postprocessor
            self.measurement = None
            self.df = None
            self.nofork = False

        def execute(self):
            self.measurement, self.df = self.postprocessor(self.filepath)
            self.result = self.df
            self.final = True
            log.debug(f"New {self.measurement}")

        def subset_map(self):
            return super().subset_map()

    class Untar(Task_Message):

        def __init__(self, ID, filepath):
            Task_Message.__init__(self, ID, filepath)
            self.result = None

        def decompress(self):
            with tarfile.open(self.filepath) as tar:
                try:
                    tar.extractall(self.filepath.parent)
                    self.result = self.filepath
                    log.debug(f"Successfully extracted {self.result}")
                except Exception as e:
                    log.error(f"Task ID: {self.ID} {self.filepath} could not be untarred: {e} ")
                os.sync()

        def execute(self):
            self.decompress()

        def subset_map(self):
            return super().subset_map()

    class Bz2_Decompress(Task_Message):
        def __init__(self, ID, filepath):
            Task_Message.__init__(self, ID, filepath)
            self.nofork = False

        def execute(self):
            self.decompress()
            return self.result

        def decompress(self):
            with bz2.open(self.filepath) as f:
                try:
                    with open(self.filepath.with_suffix(''), 'wb') as g:
                        g.write(f.read())
                        self.result = self.filepath
                        log.debug("Successfully decompressed {self.result}")
                except Exception as e:
                    log.warn(f"Task ID:{self.ID} {self.filepath} could not be decompressed: {e}")
                f.flush()
                f.close()
                os.sync()

        def subset_map(self):
            return super().subset_map()


class Tansformer(ABC):
    @abstractmethod
    def transform(task_from, associations=[]):
        pass


class Task_Transformers:

    class File_Reassembly:
        class S3_File_Upload(Tansformer):
            @staticmethod
            def transform(task_from, filename_filters=['.*'], config=None):
                log.debug("Transforming to S3 File Upload")
                if not task_from.result:
                    return
                filename = Path(task_from.filepath).name
                if not any_regex_matches(str(filename), filename_filters):
                    return
                filepath = Path(task_from.filepath)
                ground_tag = task_from.ground_tag
                pass_id = task_from.pass_id
                sv_name = task_from.sv_name
                aws_bucket = deep_get(task_from.config, 'instance.global.aws_bucket')
                aws_region = deep_get(task_from.config, 'instance.global.aws_region')
                s3_path = f"data/{pass_id}/{sv_name}/file_downlink/{ground_tag}/{filename}"
                
                res = []
                upload_file = Tasks.S3_File_Upload(task_from.ID,
                                                   aws_bucket,
                                                   filepath,
                                                   s3_path,
                                                   aws_region,
                                                   ground_tag,
                                                   config=task_from.config)
                res.append(upload_file)

                if task_from.md5_file:
                    filename = Path(task_from.md5_file).name
                    s3_path = f"data/{pass_id}/{sv_name}/file_downlink/{ground_tag}/{filename}"
                    upload_md5 = Tasks.S3_File_Upload(task_from.ID,
                                                      aws_bucket,
                                                      str(task_from.md5_file),
                                                      s3_path,
                                                      aws_region,
                                                      ground_tag,
                                                      config=task_from.config)
                    res.append(upload_md5)
                return res

        class Untar(Tansformer):
            @staticmethod
            def transform(task_from, filename_filters=[r'.*\.(tar)$']):
                filename = Path(task_from.filepath)
                log.debug(f'Found filename: {filename.name}')
                if any_regex_matches(str(filename.name), filename_filters):
                    log.debug(f"Transforming file reassembly task to untar: {filename}.")
                    filepath = task_from.filepath
                    return Tasks.Untar(task_from.ID, filepath)
                return None

    class Untar:
        class Bz2_Decompress(Tansformer):
            @staticmethod
            def transform(task_from, filename_filters=[r'.*\.(bz2)$']):
                new_tasks = []
                matches = regex_filter_dir_for_files(task_from.filepath.parent, filename_filters)
                i = 0
                for f in matches:
                    new_task_id = f"{str(task_from.ID)}_{str(i)}"
                    log.debug(f"Task ID: {new_task_id} Transforming untar to bz2 uncompress: {f}")
                    new_tasks.append(Tasks.Bz2_Decompress(new_task_id, f))
                    i += 1
                return new_tasks

    class Bz2_Decompress:
        class Post_Process(Tansformer):
            @staticmethod
            def transform(from_task, post_processors=[], filename_filters=[], args={}):
                new_tasks = []
                log.debug(from_task.filepath.parent)
                matches = regex_filter_dir_for_files(from_task.filepath.parent, filename_filters)
                for f in matches:
                    for post_processor in args['processor']:
                        module = importlib.import_module(f"bifrost.PostProcessors.{post_processor}")
                        post_processor = getattr(module, 'process')

                        task = Tasks.CSV_to_Influx(from_task.ID,
                                                   f,
                                                   post_processor)
                        new_tasks.append(task)
                        log.debug(f"Task ID: {task.ID} Created new postprocessor task: {module}")
                return new_tasks


def regex_filter_dir_for_files(path, regex_filters):
    files = list(Path(path).glob('**/*'))
    log.debug(f"Globbed path: {path}")
    log.debug(f"Found globbed files {files}")
    files = [f for f in files if f.is_file()]
    log.debug(f"Found files {files}")
    regex_filters = compile_regex_filters(regex_filters)
    matches = set(i for p in regex_filters for i in files if p.match(str(i.name)))
    log.debug(f"Found {matches}")
    return matches


def compile_regex_filters(filters):
    regex_filters = set()
    for p in filters:
        try:
            regex_filters.add(re.compile(p))
        except re.error:
            log.error(f"Invalid regex {p}, skipping filter.")
        except Exception as e:
            log.error(f"Error during regex compiliation, skipping filter: {e}")
    log.debug(regex_filters)
    return regex_filters


def any_regex_matches(string, regex_filters):
    if not regex_filters or not string:
        return False
    regex_filters = compile_regex_filters(regex_filters)
    matches = any(p.match(string) for p in regex_filters)
    log.debug(f"{string}, {regex_filters}, {matches}")
    return matches
