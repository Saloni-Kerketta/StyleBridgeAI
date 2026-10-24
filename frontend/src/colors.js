// Swatch colours for product cards (product images are placeholders in the synthetic data).
export const COLOUR_HEX = {
  "Powder Blue": "#B8D4EA", "Mint Green": "#BFE6D3", "Blush Pink": "#F4CAD3", Lavender: "#D4C8EC", Peach: "#F8D3B8",
  "Lemon Yellow": "#F6EDA0", Lilac: "#CDB7E0", "Sage Green": "#B7C7A8", White: "#FFFFFF", "Off-White": "#F4F1E8",
  Beige: "#DCC9A8", Cream: "#F5EBCF", Grey: "#A5ABB3", Black: "#1D1F23", Navy: "#1F2F54", Tan: "#C49A6C",
  Red: "#C8282E", "Royal Blue": "#2A52BE", "Emerald Green": "#168A5A", Mustard: "#D6A520", Coral: "#EE6F5C",
  Orange: "#E8731A", Fuchsia: "#C2287F", Teal: "#127C80", Olive: "#6F7138", Rust: "#A8481F", Brown: "#6B4426",
  Maroon: "#6E1B2B", Khaki: "#B5A36B", Terracotta: "#C46A4A", "Light Wash Denim": "#8EAAC9", "Dark Wash Denim": "#2F4668",
};

export function textOn(hex) {
  const n = parseInt(hex.slice(1), 16);
  const lum = (0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255;
  return lum > 0.62 ? "#12202F" : "#FFFFFF";
}

export const MODEL_LABELS = {
  similar_shoppers: "Shoppers like you", popularity: "Most popular", content: "Content-based", als: "Collaborative (ALS)",
};
export const DOMAIN_LABELS = { clothing: "Clothing", accessories: "Footwear & accessories" };
export const CATEGORIES_BY_DOMAIN = {
  clothing: ["top", "bottom", "dress", "ethnic_set", "outerwear"],
  accessories: ["footwear", "accessory", "bag"],
};
export const OCCASIONS = ["casual", "college", "office", "formal", "party", "wedding", "festive", "date_night", "beach", "travel", "photoshoot", "interview"];
export const FAMILIES = ["pastel", "neutral", "bright", "earthy", "denim"];
export const pretty = (s) => s.replace(/_/g, " ");
export const inr = (n) => "₹" + n.toLocaleString("en-IN");
