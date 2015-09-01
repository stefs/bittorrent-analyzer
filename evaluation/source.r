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

aggregate_time <- function(request, all_torrents) {
	# Aggregate by torrent id and last seen
	values_df <- data.frame(total=request$received_peers, duplicate=request$duplicate_peers)
	if (all_torrents) {
		groups <- list(group_hour=request$timestamp, group_source=request$source)
	} else {
		groups <- list(group_hour=request$timestamp, group_source=request$source, group_torrent=request$torrent)
	}
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

merge_peers <- function(request, all_torrents) {
	# use group_torrent depending on all_peers
	if (all_torrents) {
		gt <- rep(NaN, length(request$group_hour))
	} else {
		gt <- request$group_torrent
	}
	# assemble duplicate part
	duplicate <- data.frame(
		group_hour=request$group_hour,
		group_torrent=gt,
		peers=request$duplicate,
		source=request$group_source,
		status="duplicate"
	)
	# assemble new part
	new <- data.frame(
		group_hour=request$group_hour,
		group_torrent=gt,
		peers=request$new,
		source=request$group_source,
		status="unique"
	)
	# merge parts vertically
	request <- rbind(duplicate, new)
	# factorize for custom order
	request$source <- factor(request$source, levels=c(
		"tracker",
		"dht",
		"incoming"
	))
	request$status <- factor(request$status, levels=c(
		"unique",
		"duplicate"
	))
	# Return result
	return(request)
}

plot_source <- function(data, title=NULL) {
	# Plot with ggplot2 with bar order according to category
	print(
		ggplot(data, aes(x=factor(group_hour), y=peers, fill=source, order=as.numeric(source))) +
		geom_bar(stat="identity", position="stack") +
		facet_grid(status ~ .) +
		theme(axis.text.x=element_text(angle=90, hjust=1)) +
		labs(title=title, x="Time UTC (month/day/hour)", y="Peers")
	)
}

# Read database
args <- commandArgs(trailingOnly=TRUE)
all_torrents <- args[1] == "sum"
ret <- read_db(args[2])
request <- ret[[1]]
torrent <- ret[[2]]

# Prepare data
print(head(request))
print(head(torrent))
print("*** Parse timesamps ***")
request$timestamp <- hour_timestamps(request$timestamp)
print(head(request))
print("*** Aggregate timestamp ***")
request <- aggregate_time(request, all_torrents)
print(head(request))
print("*** Calculate new peers ***")
request <- new_peers(request)
print(head(request))
print("*** Merge peer numbers ***")
request <- merge_peers(request, all_torrents)
print(head(request))

# Data per torrent
if (all_torrents) {
	suffix = "_source_all_torrents.pdf"
} else {
	suffix = "_source_per_torrent.pdf"
}
outfile = sub(".sqlite", suffix, args[2])
stopifnot(outfile != args[2])
pdf(outfile, width=9, height=4)

# Decide if summary of all torrents or plot per torrent
if (all_torrents) {
	plot_source(request)
} else {
	for (id in unique(request$group_torrent)) {
		# Make description
		info <- torrent[torrent$id==id,]
		description <- torrent_description(id, info$display_name, info$gigabyte)
		print(description)

		# Plot current torrent
		filtered <- filter_request(request, id)
		print(head(filtered))
		plot_source(filtered, title=description)
	}
}
print(paste("Plot written to", outfile))
print("*** End ***")
