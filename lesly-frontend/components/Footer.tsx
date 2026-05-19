export default function Footer() {
  return (
    <footer className="border-t border-slate-800 bg-[#02030b] py-10 text-slate-400">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-6 text-sm sm:flex-row sm:items-center sm:justify-between lg:px-10">
        <div>
          <p className="text-lg font-semibold text-white">Lesly AI Trading</p>
          <p className="mt-2 max-w-xl text-slate-500">
            This platform is for educational and paper trading purposes only. No real trades are executed.
          </p>
        </div>
        <p className="text-slate-500">© 2026 Lesly Labs. All rights reserved.</p>
      </div>
    </footer>
  );
}
