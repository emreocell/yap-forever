import os
import tempfile

# Keep every test away from the real player folder: anything that falls back to the
# default home lands in a throwaway directory instead.
os.environ["YAP_FOREVER_HOME"] = tempfile.mkdtemp(prefix="yap-forever-tests-")
