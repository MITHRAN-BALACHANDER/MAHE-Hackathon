type AlertBannerProps = {
  message?: string;
  fallback?: string;
};

export function AlertBanner({ message, fallback }: AlertBannerProps) {
  if (!message && !fallback) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-amber-300/30 bg-amber-300/10 px-4 py-3 text-sm text-amber-100">
      <span className="font-semibold">Network Alert:</span>{" "}
      {message ?? fallback}
    </div>
  );
}
