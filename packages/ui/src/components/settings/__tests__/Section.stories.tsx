import type { Meta, StoryObj } from '@storybook/react';
import { Section } from '../Section';
import { SettingRow } from '../SettingRow';

const meta: Meta<typeof Section> = { title: 'Primitives/Section', component: Section };
export default meta;

export const Basic: StoryObj<typeof Section> = {
  render: () => (
    <Section title="General">
      <SettingRow label="One" id="sec-one" control={<input id="sec-one" type="checkbox" />} />
      <SettingRow label="Two" description="With description" id="sec-two" control={<input id="sec-two" type="checkbox" />} />
      <SettingRow label="Three" id="sec-three" control={<input id="sec-three" type="checkbox" />} last />
    </Section>
  ),
};

export const Untitled: StoryObj<typeof Section> = {
  render: () => (
    <Section>
      <SettingRow label="Solo row" id="sec-solo" control={<input id="sec-solo" type="checkbox" />} last />
    </Section>
  ),
};
