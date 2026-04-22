"use client";

import { MessageSquare, ExternalLink } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import Image from "next/image";
import type { Discussion } from "../lib/github";
import { Button } from "@prep/ui";

interface DiscussionListProps {
  discussions: Discussion[];
}

export function DiscussionList({ discussions }: DiscussionListProps) {
  if (discussions.length === 0) {
    return (
      <div className="text-center py-12 border border-dashed border-border rounded-lg">
        <MessageSquare className="w-12 h-12 text-text-muted mx-auto mb-4" />
        <h3 className="text-lg font-medium text-text">No discussions found</h3>
        <p className="text-text-muted mt-2">
          Be the first to start a discussion on GitHub!
        </p>
        <div className="mt-6">
          <Button asChild>
            <a href="https://github.com/MagneticAnomaly/SourcePrep-MCP/discussions" target="_blank" rel="noopener noreferrer">
              View all discussions &rarr;
            </a>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-text">Community Discussions</h2>
        <Button variant="outline" size="sm" asChild>
          <a href="https://github.com/MagneticAnomaly/SourcePrep-MCP/discussions" target="_blank" rel="noopener noreferrer" className="gap-2">
            View all on GitHub <ExternalLink className="w-4 h-4" />
          </a>
        </Button>
      </div>
      
      <div className="grid gap-4">
        {discussions.map((discussion) => (
          <a 
            key={discussion.id} 
            href={discussion.url}
            target="_blank" 
            rel="noopener noreferrer"
            className="group block p-5 bg-surface border border-border rounded-lg hover:border-primary/50 hover:bg-surface-raised transition-all"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-xs text-text-subtle mb-1">
                  <span className="flex items-center gap-1 bg-surface px-1.5 py-0.5 rounded border border-border">
                    {discussion.category.emoji} {discussion.category.name}
                  </span>
                  <span>•</span>
                  <span>{formatDistanceToNow(new Date(discussion.createdAt), { addSuffix: true })}</span>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    by <Image src={discussion.author.avatarUrl} alt={discussion.author.login} width={16} height={16} className="rounded-full" /> {discussion.author.login}
                  </span>
                </div>
                <h3 className="text-lg font-medium text-text group-hover:text-primary transition-colors line-clamp-1">
                  {discussion.title}
                </h3>
                <p className="text-sm text-text-muted line-clamp-2">
                  {discussion.bodyText}
                </p>
              </div>
              
              <div className="flex items-center gap-1 text-text-subtle bg-surface px-2 py-1 rounded-full text-xs shrink-0">
                <MessageSquare className="w-3.5 h-3.5" />
                <span>{discussion.comments.totalCount}</span>
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
