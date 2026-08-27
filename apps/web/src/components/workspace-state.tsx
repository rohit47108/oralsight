import Link from "next/link";

export function WorkspaceState({
  title,
  body,
  action,
  headingLevel = "h2",
}: {
  title: string;
  body: string;
  action?: { href: string; label: string };
  headingLevel?: "h1" | "h2" | "h3";
}) {
  const Heading = headingLevel;

  return (
    <section className="workspace-state">
      <span className="workspace-state__mark" aria-hidden="true">
        i
      </span>
      <div>
        <Heading>{title}</Heading>
        <p>{body}</p>
        {action ? (
          <Link className="text-link" href={action.href}>
            {action.label}
          </Link>
        ) : null}
      </div>
    </section>
  );
}
