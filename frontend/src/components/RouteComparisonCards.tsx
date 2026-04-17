import type { RouteOption } from "@/src/types/route";

import { RouteCard } from "./RouteCard";

type RouteComparisonCardsProps = {
  routes: RouteOption[];
  recommendedRoute: string;
};

export function RouteComparisonCards({
  routes,
  recommendedRoute,
}: RouteComparisonCardsProps) {
  return (
    <section className="grid gap-4 lg:grid-cols-3">
      {routes.map((route) => (
        <RouteCard
          key={route.name}
          route={route}
          isRecommended={route.name === recommendedRoute}
        />
      ))}
    </section>
  );
}
