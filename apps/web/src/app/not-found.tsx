import Link from "next/link";

export default function NotFound() {
  return (
    <section className="state-page page-width">
      <p className="section-label">404</p>
      <h1>That page is not here.</h1>
      <p>The link may have expired or the address may be incomplete.</p>
      <Link className="button" href="/">
        Return home
      </Link>
    </section>
  );
}
