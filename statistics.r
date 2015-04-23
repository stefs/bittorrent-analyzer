#!/usr/bin/env Rscript

library(DBI)

read_db <- function(path){
	# Open raw_peersbase connection
	con <- dbConnect(RSQLite::SQLite(), path)
	# Disable auto commit
	dbBegin(con)
	# Execute SQL
	sql <- "SELECT first_pieces, last_pieces, last_seen, torrent FROM peer"
	peers <- dbGetQuery(con, sql)
	# Close database connection
	dbDisconnect(con)
	# Return result
	return(peers)
}

filter_peers <- function(peers){
	# Filter for usable last pieces
	peers <- peers[complete.cases(peers$last_pieces),]
	# Add pieces delta and filter for positive delta
	peers$pieces_delta <- peers$last_pieces - peers$first_pieces
	peers <- peers[peers$pieces_delta>0,]
	# Drop first and last pieces
	peers$first_pieces <- NULL
	peers$last_pieces <- NULL
	# Parse timestamps and truncate to hours
	peers$last_seen <- as.POSIXct(peers$last_seen, tz="GMT")
	peers$last_seen <- trunc(peers$last_seen, units="hours")
	peers$last_seen <- as.character(peers$last_seen)
	# Return result
	return(peers)
}

aggregate_time <- function(peers){
	# Aggregate by last seen and torrent
	values_df <- data.frame(pieces_delta=peers$pieces_delta)
	groups <- list(last_seen=peers$last_seen, torrent=peers$torrent)
	aggregated_peers <- aggregate(values_df, by=groups, FUN=sum)
	# Return result
	return(aggregated_peers)
}

plot_downloads_t1 <- function(peers){
	# Filter for first torrent
	peers <- peers[peers$torrent==1,]
	# Create barplot
	values <- peers$pieces_delta
	names(values) <- peers$last_seen
	barplot(values)
}

print("*** Head of raw peers ***")
peers <- read_db("output/2015-04-16_11-26-46_faui1-246.sqlite")
print(head(peers))
print("*** Head of filtered peers ***")
peers <- filter_peers(peers)
print(head(peers))
print("*** Aggregated downloads ***")
peers <- aggregate_time(peers)
print(peers)
print("*** Plot downloads ***")
plot_downloads_t1(peers)
print("*** End ***")

