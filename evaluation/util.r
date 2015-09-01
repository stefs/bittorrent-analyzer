hour_timestamps <- function(timestamps) {
	# Parse timestamps
	timestamps <- as.POSIXct(timestamps, tz="GMT", origin="1970-01-01")
	# Truncate to hours
	timestamps <- trunc(timestamps, units="hours")
	# Revert to strings
	timestamps <- strftime(timestamps, format="%m/%d/%H")
	# Return result
	return(timestamps)
}

torrent_description <- function(id, display_name, gigabyte) {
	# Trim to 50 characters
	name <- strtrim(display_name, 50)
	# Round size to one digit
	size <- round(gigabyte, digits=1)
	# Assemble with format stirng
	description <- paste("Torrent ", id, ": \"", name, "\" (", size, " GB)", sep="")
	# Return result
	return(description)
}
