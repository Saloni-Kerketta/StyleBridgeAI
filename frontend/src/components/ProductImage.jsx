import React, { useEffect, useState } from "react";
import { fetchProductImage, withUtm } from "../imageApi.js";
import { COLOUR_HEX, textOn } from "../colors.js";

/** Photo fetched with axios; shows a colour swatch while loading or if no photo is available. */
export default function ProductImage({ item, size = "default" }) {
  const [photo, setPhoto] = useState(null);
  const [broken, setBroken] = useState(false);
  const height = { compact: "h-28", default: "h-56", featured: "h-56 md:h-full md:min-h-[18rem]" }[size];

  useEffect(() => {
    let live = true;
    setPhoto(null);
    setBroken(false);
    fetchProductImage(item).then((p) => live && setPhoto(p));
    return () => { live = false; };
  }, [item.colour, item.subcategory]);

  if (photo && !broken) {
    return (
      <div className={`relative ${height} bg-paper`}>
        <img src={photo.url} alt={`${item.name} (illustrative photo)`} loading="lazy" onError={() => setBroken(true)}
          className="h-full w-full object-cover" />
        <p className="absolute bottom-1 left-1 right-1 truncate rounded bg-black/55 px-1.5 py-0.5 text-[10px] text-white">
          Photo by <a className="underline" href={withUtm(photo.profile)} target="_blank" rel="noreferrer">{photo.photographer}</a> on{" "}
          <a className="underline" href={withUtm("https://unsplash.com")} target="_blank" rel="noreferrer">Unsplash</a>
        </p>
      </div>
    );
  }
  const hex = COLOUR_HEX[item.colour] || "#DCE2EA";
  return (
    <div role="img" aria-label={`${item.name}, ${item.colour}`} className={`${height} flex flex-col justify-end p-3`}
      style={{ background: hex, color: textOn(hex) }}>
      <p className="font-display text-lg font-medium leading-tight">{item.subcategory}</p>
      <p className="text-xs opacity-80">{item.colour}</p>
    </div>
  );
}
