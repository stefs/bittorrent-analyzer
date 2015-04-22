class AnalyzerError(Exception):
	pass

class FileError(AnalyzerError):
	pass

class DHTError(AnalyzerError):
	pass

class TrackerError(AnalyzerError):
	pass

class DatabaseError(AnalyzerError):
	pass

