import Link from "next/link";

export function WorkspaceState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: { href: string; label: string };
}) {
  return (
    <section className="workspace-state">
      <span className="workspace-state__mark" aria-hidden="true">
        i
      </span>
      <div>
        <h2>{title}</h2>
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
