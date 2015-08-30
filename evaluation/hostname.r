#!/usr/bin/env Rscript

library(DBI)
library(ggplot2)
library(plyr)

read_db <- function(path, torrent_set) {
	# Open raw_peersbase connection
	con <- dbConnect(RSQLite::SQLite(), path)
	# Disable auto commit
	dbBegin(con)
	# Read peer table
	sql <- "SELECT host FROM peer"
	host <- dbGetQuery(con, sql)
	# Close database connection
	dbDisconnect(con)
	# Combine tables
	ret <- list(host)
	# Return result
	return(ret)
}

remove_ip <- function(name) {
	part <- unlist(strsplit(name, "-"))
	number <- as.integer(part)
	keep <- is.na(number) | number >= 256
	main <- part[keep]
	short <- paste(main, collapse="-")
	return(short)
}

aggregate_host <- function(host) {
	values_df <- data.frame(freq=host$freq)
	groups <- list(x=host$x)
	ret <- aggregate(values_df, by=groups, FUN=sum)
}

# Read database
args <- commandArgs(trailingOnly=TRUE)
ret <- read_db(args[1])
host <- ret[[1]]

# Remove NAs from host names
host <- host[complete.cases(host),]
# Count frequency of host names
host <- count(host)
# Remove ip prefix and TLD from host names
x <- c()
for (name in host$x) {
	x <- c(x, remove_ip(name))
}
host$x <- x
# Aggregate now equal host names
host <- aggregate_host(host)
# Get top host names
host <- host[order(-host$freq),]
host <- head(host, n=50)
# Set factor order to data frame order
host$x <- factor(host$x, host$x)
print(host)

# Create file for ggplot
outfile = sub(".sqlite", "_hostnames.pdf", args[1])
stopifnot(outfile != args[1])
pdf(outfile, width=9, height=3.75)

# Plot with ggplot2
print(
	ggplot(data=host, aes(x=x, y=freq)) +
	geom_bar(stat="identity") +
	labs(x="Hostname", y="Peers") +
	theme(axis.text.x=element_text(angle=90, hjust=1))
)
print(paste("Plot written to", outfile))


print("*** End ***")
