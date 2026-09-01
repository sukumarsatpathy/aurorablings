import { Link } from 'react-router-dom';

/**
 * Any unmatched URL.
 *
 * Without this the router matched nothing and rendered nothing, so a typo — or a
 * route that exists in source but not in the build being served — showed a blank
 * white page with no clue as to why. A page that says what happened turns ten
 * minutes of confusion into a glance.
 */
export function NotFoundPage() {
  return (
    <div className="grid min-h-[70vh] place-items-center px-6 text-center">
      <div>
        <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">404</p>
        <h1 className="mt-3 text-2xl font-semibold">This page doesn’t exist</h1>
        <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
          The address {window.location.pathname} didn’t match anything. If you expected a
          page here, the running build may be older than the code.
        </p>
        <Link
          to="/"
          className="mt-6 inline-block rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground"
        >
          Back to the shop
        </Link>
      </div>
    </div>
  );
}

export default NotFoundPage;
