from digiskr.base import BaseSoundRecorder, DecoderQueue, Option, AudioDecoderProfile, QueueJob
from digiskr.parser import LineParser
import subprocess
import logging, os
from queue import Full


class WsjtSoundRecorder(BaseSoundRecorder):
    def __init__(self, options: Option, profile: AudioDecoderProfile, parser: LineParser):
        super(WsjtSoundRecorder, self).__init__(options, profile, parser)

    def pre_decode(self):
        filename = self._get_output_filename()
        job = QueueJob(self, filename, self._freq)
        try:
            logging.debug("put a new job into queue %s", filename)
            DecoderQueue.instance().put(job)
        except Full:
            logging.error("decoding queue overflow; dropping one file")
            job.unlink()

    def decode(self, job: QueueJob):
        logging.info("processing file %s", job.file)
        file = os.path.realpath(job.file)
        decoder = subprocess.Popen(
            ["nice", "-n", "10"] + self._profile.decoder_commandline(file),
            stdout=subprocess.PIPE,
            cwd=os.path.dirname(file),
            close_fds=True,
            )
        
        messages = []
        for line in decoder.stdout:
            messages.append((job.freq, line))
        self._parser.setStation(self._options.station)
        self._parser.parse(messages)
        
        try:
            rc = decoder.wait(timeout=10)
            if rc != 0:
                logging.warning("decoder return code: %i", rc)
        except subprocess.TimeoutExpired:
            logging.warning("subprocess (pid=%i}) did not terminate correctly; sending kill signal.", decoder.pid)
            decoder.kill()
