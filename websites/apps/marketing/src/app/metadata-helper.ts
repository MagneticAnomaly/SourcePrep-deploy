import { Metadata } from 'next';

type MetaProps = {
  title: string;
  description: string;
  path: string;
};

export function constructMetadata({ title, description, path }: MetaProps): Metadata {
  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: `https://runprep.io${path}`,
      siteName: 'RunPrep',
      images: [
        {
          url: 'https://runprep.io/images/og-image.png',
          width: 1245,
          height: 779,
          alt: title,
        },
      ],
      locale: 'en_US',
      type: 'website',
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
      images: ['https://runprep.io/images/og-image.png'],
    },
  };
}
