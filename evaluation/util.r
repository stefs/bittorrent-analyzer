hour_timestamps <- function(timestamps) {
	# Parse timestamps
	timestamps <- as.POSIXct(timestamps, tz="GMT", origin="1970-01-01")
	# Truncate to hours
	timestamps <- trunc(timestamps, units="hours")
	# Revert to strings
	timestamps <- strftime(timestamps, format="%d/%H")
	# Return result
	return(timestamps)
}
