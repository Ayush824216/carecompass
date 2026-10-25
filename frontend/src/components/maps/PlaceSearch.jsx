import { useEffect, useRef } from "react";

/** Google Places Autocomplete limited to India. Uses the new PlaceAutocompleteElement, else the classic widget. */
export default function PlaceSearch({ g, id, placeholder, onPlace }) {
  const host = useRef(null);
  const cb = useRef(onPlace);
  cb.current = onPlace;

  useEffect(() => {
    const P = g.maps.places;
    if (!P) return undefined;
    if (P.PlaceAutocompleteElement) {
      const el = new P.PlaceAutocompleteElement({ includedRegionCodes: ["in"] });
      el.id = id;
      el.setAttribute("placeholder", placeholder);
      el.style.width = "100%";
      el.style.colorScheme = "light";
      const onSelect = async (e) => {
        try {
          const place = e.placePrediction ? e.placePrediction.toPlace() : e.place;
          await place.fetchFields({ fields: ["displayName", "formattedAddress", "location"] });
          if (place.location) cb.current({ lat: place.location.lat(), lng: place.location.lng(), label: place.displayName || place.formattedAddress || "" });
        } catch { /* ignore a failed lookup; the user can search again or drop a pin */ }
      };
      el.addEventListener("gmp-select", onSelect);
      el.addEventListener("gmp-placeselect", onSelect); // older event name
      host.current.append(el);
      return () => el.remove();
    }
    const input = document.createElement("input");
    input.id = id;
    input.className = "input";
    input.placeholder = placeholder;
    host.current.append(input);
    const ac = new P.Autocomplete(input, { componentRestrictions: { country: "in" }, fields: ["geometry", "name", "formatted_address"] });
    const l = ac.addListener("place_changed", () => {
      const p = ac.getPlace();
      const loc = p?.geometry?.location;
      if (loc) cb.current({ lat: loc.lat(), lng: loc.lng(), label: p.name || p.formatted_address || "" });
    });
    return () => { l.remove(); input.remove(); };
  }, [g, id, placeholder]);

  return <div ref={host} className="w-full" />;
}
