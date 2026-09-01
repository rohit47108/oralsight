export const SITE_NAME = "Stoma3D";
export const DISCLAIMER = "This result is not a diagnosis.";

export const primaryNavigation = [
  { href: "/how-it-works", label: "How it works" },
  { href: "/privacy", label: "Privacy" },
  { href: "/for-professionals", label: "For professionals" },
  { href: "/research", label: "Analysis & evidence" },
] as const;

export const footerNavigation = [
  { href: "/calibration", label: "Calibration card" },
  { href: "/security", label: "Security" },
  { href: "/accessibility", label: "Accessibility" },
  { href: "/research", label: "Analysis & evidence" },
] as const;

export const mouthRegions = [
  { id: "dorsal_tongue", label: "Top of tongue", number: "01" },
  { id: "ventral_tongue", label: "Under the tongue", number: "02" },
  { id: "left_buccal_mucosa", label: "Inside left cheek", number: "03" },
  { id: "right_buccal_mucosa", label: "Inside right cheek", number: "04" },
  { id: "upper_lip", label: "Inside upper lip", number: "05" },
  { id: "lower_lip", label: "Inside lower lip", number: "06" },
  { id: "upper_dental_arch", label: "Upper teeth and gums", number: "07" },
  { id: "lower_dental_arch", label: "Lower teeth and gums", number: "08" },
] as const;

export type MouthRegionId = (typeof mouthRegions)[number]["id"];

export const scanSteps = [
  {
    title: "Consent",
    summary: "Choose what you record and review the privacy choices first.",
  },
  {
    title: "Capture eight regions",
    summary: "Follow one fixed path so every session covers the same areas.",
  },
  {
    title: "Review observations",
    summary:
      "Check image quality, visible descriptors, uncertainty, and limits.",
  },
  {
    title: "Save or share a report",
    summary: "Keep a local PDF or create time-limited access when you choose.",
  },
] as const;
