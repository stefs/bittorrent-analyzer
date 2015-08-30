#!/usr/bin/env Rscript

library(DBI)
library(ggplot2)
library(plyr)

# Read csv
args <- commandArgs(trailingOnly=TRUE)
tracker <- read.csv(args[1], header=FALSE)
names(tracker) <- c("torrent", "tracker", "result", "reason", "count")

# Sum per tracker
values_df <- data.frame(count=as.integer(tracker$count))
groups <- list(torrent=tracker$torrent, result=tracker$result)
tracker <- aggregate(values_df, by=groups, FUN=sum)

# Distinguish between announce vs. scrape
tracker$event <- unlist(lapply(strsplit(as.character(tracker$result), " "), "[", 1))
tracker$status <- unlist(lapply(strsplit(as.character(tracker$result), " "), "[", 2))
tracker$result <- NULL
print(head(tracker))

# Create file
outfile = sub(".txt", ".pdf", args[1])
stopifnot(outfile != args[1])
pdf(outfile, width=9, height=3)

# Plot with ggplot2
print(
	ggplot(tracker, aes(x=factor(torrent), y=count, fill=status)) +
	geom_bar(stat="identity", position="dodge") +
	facet_grid(event ~ ., scales="free_y") +
	labs(x="Torrent", y="Requests")
)
print(paste("Plot written to", outfile))
print("*** End ***")
