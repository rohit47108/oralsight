type PageIntroProps = {
  label: string;
  title: string;
  description: string;
};

export function PageIntro({ label, title, description }: PageIntroProps) {
  return (
    <header className="page-intro page-width">
      <p className="section-label">{label}</p>
      <h1>{title}</h1>
      <p className="page-intro__description">{description}</p>
    </header>
  );
}
