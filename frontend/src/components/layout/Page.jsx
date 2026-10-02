import { MobileBar } from "../chat/AskView.jsx";

export default function Page({ onMenu, wide, children }) {
  return (
    <div className="h-full overflow-y-auto">
      <MobileBar onMenu={onMenu} />
      <div className={`mx-auto px-4 py-8 sm:px-8 sm:py-12 ${wide ? "max-w-6xl" : "max-w-3xl"}`}>{children}</div>
    </div>
  );
}
