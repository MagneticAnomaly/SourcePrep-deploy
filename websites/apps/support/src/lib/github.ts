import { graphql } from "@octokit/graphql";
import type { GraphQlQueryResponseData } from "@octokit/graphql";

const REPO_OWNER = 'EricBintner';
const REPO_NAME = 'Prep';

// Use a read-only token if available, otherwise rely on public access if possible (GraphQL requires token usually)
const GITHUB_TOKEN = process.env.GITHUB_TOKEN;

const graphqlWithAuth = graphql.defaults({
  headers: {
    authorization: `token ${GITHUB_TOKEN}`,
  },
});

export interface Discussion {
  id: string;
  title: string;
  url: string;
  createdAt: string;
  bodyText: string;
  author: {
    login: string;
    avatarUrl: string;
  };
  category: {
    name: string;
    emoji: string;
  };
  comments: {
    totalCount: number;
  };
}

export async function getRecentDiscussions(first: number = 5): Promise<Discussion[]> {
  if (!GITHUB_TOKEN) {
    console.warn("GITHUB_TOKEN is not set. Returning mock data or empty list.");
    return [];
  }

  try {
    const { repository } = await graphqlWithAuth<GraphQlQueryResponseData>(`
      query($owner: String!, $name: String!, $first: Int!) {
        repository(owner: $owner, name: $name) {
          discussions(first: $first, orderBy: {field: CREATED_AT, direction: DESC}) {
            nodes {
              id
              title
              url
              createdAt
              bodyText
              author {
                login
                avatarUrl
              }
              category {
                name
                emoji
              }
              comments {
                totalCount
              }
            }
          }
        }
      }
    `, {
      owner: REPO_OWNER,
      name: REPO_NAME,
      first,
    });

    return repository.discussions.nodes;
  } catch (error) {
    console.error("Failed to fetch discussions:", error);
    return [];
  }
}
