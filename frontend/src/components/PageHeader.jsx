export default function PageHeader({ eyebrow, title, subtitle, children }) {
  return (
    <section className="border-b border-line bg-sunken/50">
      <div className="container-page py-10 md:py-14">
        {eyebrow && <p className="eyebrow mb-3">{eyebrow}</p>}
        <h1 className="text-3xl font-semibold md:text-5xl">{title}</h1>
        {subtitle && <p className="mt-3 max-w-3xl text-lg text-muted">{subtitle}</p>}
        {children}
      </div>
    </section>
  );
}
