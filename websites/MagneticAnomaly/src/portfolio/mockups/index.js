// Variant map: mockup.type string -> component. <Panel> looks up the variant
// here and renders it, passing `innerClass` + the spread mockup props.

import DesktopBrowserMockup from './DesktopBrowserMockup';
import DualPhoneImageMockup from './DualPhoneImageMockup';
import DualPhonePlaceholderMockup from './DualPhonePlaceholderMockup';

export const mockupVariants = {
  'desktop-browser': DesktopBrowserMockup,
  'dual-phone-image': DualPhoneImageMockup,
  'dual-phone-placeholder': DualPhonePlaceholderMockup,
};

export { default as DesktopBrowserMockup } from './DesktopBrowserMockup';
export { default as DualPhoneImageMockup } from './DualPhoneImageMockup';
export { default as DualPhonePlaceholderMockup } from './DualPhonePlaceholderMockup';