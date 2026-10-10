// Packages that import this one type-check this file too, and need the `?raw` declaration with it.
// eslint-disable-next-line @typescript-eslint/triple-slash-reference
/// <reference path="./vite-env.d.ts" />
import type { SVGProps } from "react";

import type { IconName, IllustrationName } from "./icon-names";
import { cn } from "./lib/cn";
import sprite from "./sprite.svg?raw";

/** The drawings from the prototype, as one hidden SVG. Render it once, at the top of each app. */
export function Sprite() {
  // The markup is a file of this package (sprite.svg), never user input.
  // The <svg> inside is zero-sized. `hidden` would be simpler but breaks gradients in some browsers.
  return <div aria-hidden dangerouslySetInnerHTML={{ __html: sprite }} />;
}

/** A line icon, 20 px by default, coloured by the surrounding text. Decorative unless given a label. */
export function Icon({ name, className, ...props }: { name: IconName } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      aria-hidden={props["aria-label"] ? undefined : true}
      className={cn("size-5 flex-none fill-none stroke-current", className)}
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <use href={`#i-${name}`} />
    </svg>
  );
}

/** A product or place drawing. Seafood drawings stand in for product photos until real ones exist. */
export function Illustration({ name, ...props }: { name: IllustrationName } & SVGProps<SVGSVGElement>) {
  const viewBox = name === "fridge" || name === "truck" ? "0 0 120 86" : "0 0 160 110";
  return (
    <svg aria-hidden viewBox={viewBox} {...props}>
      <use href={`#p-${name}`} />
    </svg>
  );
}
