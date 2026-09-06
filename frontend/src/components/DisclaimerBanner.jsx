export default function DisclaimerBanner({ text }) {
  return (
    <div className="bg-saffron/10 border-b border-saffron/40 text-stone-800 text-sm px-4 py-2 text-center">
      <span className="font-semibold">Information, not legal advice.</span>{" "}
      {text ||
        "IP-SAKTI Sahayak provides general information, not legal advice. Verify every citation and consult a qualified IP professional before acting."}
    </div>
  );
}
