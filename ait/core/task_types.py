from ait.core import log
from pathlib import Path
import tarfile
import bz2
from abc import ABC, abstractmethod
from tqdm import tqdm
import ait
import re
import importlib

downlink_path = Path(ait.config.get('sunrise.downlink_path'))
pass_number = ait.config.get('sunrise.pass_number')
sv_name = ait.config.get('sunrise.sv_name')
aws_bucket = ait.config.get('aws.bucket')
aws_region = ait.config.get('aws.region')
aws_profile = ait.config.get('aws.profile')


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

    def __repr__(self):
        return str(self.__dict__)

    @abstractmethod
    def execute(self):
        pass


class Tasks:

    class File_Reassembly(Task_Message):
        """ This task is run automatically with ID = downlink ID"""
        def __init__(self, filepath, ground_id, sv_name="Chessmaster-Hex", file_size=0, file_reassembler=None):
            Task_Message.__init__(self, ground_id, filepath)
            self.filename = self.filepath.name
            self.ground_id = ground_id
            self.md5_pass = False
            self.sv_name = sv_name
            self.file_reassembler = file_reassembler
            self.canonical_path = None
            self.file_size = file_size

        def subset_map(self):
            a = {"status": self.result['initialize_file_downlink_reply']['status'],
                 "md5_pass": self.md5_pass,
                 "filepath": str(self.filepath.parent / self.filename)}
            return a

        def execute(self):
            self.file_reassembler(self.filepath.parent, None, self)

    class S3_File_Upload(Task_Message):
        """
        Request FileManager to upload local path to S3 bucket.
        If this task has ID 0, then it was run automatically by AIT from a File_Reassembly_Task.
        """
        def __init__(self, ID, bucket, filepath, s3_path, s3_region, ground_id, file_size):
            Task_Message.__init__(self, ID, filepath)
            self.bucket = bucket
            self.s3_path = s3_path
            self.ground_id = ground_id
            self.s3_region = s3_region
            self.metadata = None
            self.canonical_path = None
            self.file_size = file_size

        def canonical_s3_url(self):
            if not self.result:  # S3 upload returns none when successful, contains an exception otherwise
                self.canonical_path = f"https://{self.bucket}.s3-{self.s3_region}.amazonaws.com/{self.s3_path}"
                self.metadata = {'s3_url': self.canonical_path,
                                 's3_region': self.s3_region,
                                 's3_bucket': self.bucket,
                                 's3_key': str(self.s3_path)}

        def execute(self, s3_resource):
            try:
                with tqdm(total=self.file_size, unit='bytes', unit_scale=True, desc=f"Task {self.ID} -> S3 Upload => {self.s3_path}") as pbar:
                    response = s3_resource.Bucket(self.bucket).upload_file(str(self.filepath), self.s3_path, Callback=lambda b: pbar.update(b))
                if response:
                    self.result = response
                    log.error(self.result)
            except Exception as e:
                log.error(e)
                self.result = str(e)
            self.canonical_s3_url()
            log.info(f"Task ID {self.ID} -> {self.filepath} uploaded to {self.canonical_path}")

    class CSV_to_Influx(Task_Message):
        def __init__(self, ID, filepath, postprocessor):
            Task_Message.__init__(self, ID, filepath)
            self.postprocessor = postprocessor
            self.measurement = None
            self.df = None

        def execute(self):
            self.measurement, self.df = self.postprocessor(self.filepath)
            self.result = self.df
            self.final = True

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

        def execute(self):
            self.decompress()

    class Bz2_Decompress(Task_Message):
        def __init__(self, ID, filepath):
            Task_Message.__init__(self, ID, filepath)

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


class Tansformer(ABC):
    @abstractmethod
    def transform(task_from, associations=[]):
        pass


class Task_Transformers:

    class File_Reassembly:
        class S3_File_Upload(Tansformer):
            @staticmethod
            def transform(task_from, filename_filters=['.*']):
                log.debug("Transforming to S3 File Upload")
                filename = task_from.filename
                if not any_regex_matches(str(filename), filename_filters):
                    return
                filepath = task_from.filepath
                downlink_id = task_from.ground_id
                file_size = task_from.file_size
                s3_path = f"data/{pass_number}/{sv_name}/file_downlink/{downlink_id}/{filename}"
                return Tasks.S3_File_Upload(task_from.ID, aws_bucket,
                                            filepath, s3_path, aws_region,
                                            downlink_id, file_size)

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
                        module = importlib.import_module(f"sunrise.PostProcessors.{post_processor}")
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