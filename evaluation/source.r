#!/usr/bin/env Rscript

library(DBI)
library(ggplot2)
source("util.r")

read_db <- function(path) {
	# Open raw_peersbase connection
	con <- dbConnect(RSQLite::SQLite(), path)
	# Disable auto commit
	dbBegin(con)
	# Read request table
	sql <- "SELECT timestamp, source, received_peers, duplicate_peers, torrent FROM request"
	request <- dbGetQuery(con, sql)
	# Read torrent table
	sql <- "SELECT id, display_name, gigabyte FROM torrent"
	torrent <- dbGetQuery(con, sql)
	# Close database connection
	dbDisconnect(con)
	# Combine tables
	ret <- list(request, torrent)
	# Return result
	return(ret)
}

aggregate_time <- function(request) {
	# Aggregate by torrent id and last seen
	values_df <- data.frame(total=request$received_peers, duplicate=request$duplicate_peers)
	groups <- list(group_hour=request$timestamp, group_source=request$source, group_torrent=request$torrent)
	ret <- aggregate(values_df, by=groups, FUN=sum)
	# Return result
	return(ret)
}

filter_request <- function(request, torrent) {
	# Extract all rows with that id
	request <- request[request$group_torrent==torrent,]
	# Drop torrend id
	request$group_torrent <- NULL
	# Return result
	return(request)
}

new_peers <- function(request) {
	# new peers from total and duplicate
	request$new <- request$total - request$duplicate
	# Drop total peers
	request$total <- NULL
	# Return result
	return(request)
}

merge_peers <- function(request) {
	# assemble duplicate part
	duplicate <- data.frame(
		group_hour=request$group_hour,
		group_torrent=request$group_torrent,
		peers=request$duplicate,
		category=paste("duplicate", request$group_source, sep="-")
	)
	# assemble new part
	new <- data.frame(
		group_hour=request$group_hour,
		group_torrent=request$group_torrent,
		peers=request$new,
		category=paste("new", request$group_source, sep="-")
	)
	# merge parts vertically
	request <- rbind(duplicate, new)
	# factorize category with custom order
	request$category <- factor(request$category, levels=c(
		"new-tracker",
		"new-dht",
		"duplicate-tracker",
		"duplicate-dht"
	))
	# Return result
	return(request)
}

# Read database
args <- commandArgs(trailingOnly=TRUE)
ret <- read_db(args[1])
request <- ret[[1]]
torrent <- ret[[2]]

# Prepare data
print(head(request))
print(head(torrent))
print("*** Parse timesamps ***")
request$timestamp <- hour_timestamps(request$timestamp)
print(head(request))
print("*** Aggregate timestamp ***")
request <- aggregate_time(request)
print(head(request))
print("*** Calculate new peers ***")
request <- new_peers(request)
print(head(request))
print("*** Merge peer numbers ***")
request <- merge_peers(request)
print(head(request))

# Data per torrent
outfile = sub(".sqlite", "_source.pdf", args[1])
stopifnot(outfile != args[1])
pdf(outfile, width=10.5, height=3.7)
for (id in unique(request$group_torrent)) {
	# Make description
	info <- torrent[torrent$id==id,]
	description <- torrent_description(id, info$display_name, info$gigabyte)
	print(description)

	# Extract current torrent
	filtered <- filter_request(request, id)
	print(head(filtered))

	# Plot with ggplot2 with bar order according to category
	print(
		ggplot(filtered, aes(factor(filtered$group_hour), peers, fill=category, order=as.numeric(category))) +
		geom_bar(stat="identity", position="stack") +
		theme(axis.text.x=element_text(angle=90, hjust=1)) +
		labs(title=description, x="Time UTC (day/hour)", y="Peers")
	)
}
print(paste("Plot written to", outfile))
print("*** End ***")
