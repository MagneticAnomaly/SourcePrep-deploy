import type { MDXComponents } from 'mdx/types';
import { AnimatedCLI, AnimatedIDE } from '@prep/ui';

// This file allows you to provide custom React components
// to be used in MDX files. You can import and use any
// React component you want, including inline styles.

export function useMDXComponents(components: MDXComponents): MDXComponents {
  return {
    ...components,
    AnimatedCLI: (props) => <AnimatedCLI {...props} />,
    AnimatedIDE: (props) => <AnimatedIDE {...props} />,
  };
}
