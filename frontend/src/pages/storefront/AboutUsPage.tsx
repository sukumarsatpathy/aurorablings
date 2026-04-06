import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import catalogService from '@/services/api/catalog';

const sectionTitleClass = 'text-xl md:text-2xl font-semibold text-foreground';
const bodyTextClass = 'mt-3 text-sm md:text-base leading-7 text-muted-foreground';
const listClass = 'mt-4 list-disc pl-5 text-sm md:text-base leading-7 text-muted-foreground space-y-2';

interface AboutCategory {
  id: string;
  name: string;
  is_active?: boolean;
}

export const AboutUsPage: React.FC = () => {
  const [activeCategories, setActiveCategories] = useState<string[]>([]);

  useEffect(() => {
    const loadCategories = async () => {
      try {
        const rows = (await catalogService.listAllCategories()) as AboutCategory[];
        const names = rows
          .filter((category) => category.is_active)
          .map((category) => category.name?.trim())
          .filter((name): name is string => Boolean(name));
        setActiveCategories(names);
      } catch (error) {
        console.error('Failed to load active categories for About Us page:', error);
        setActiveCategories([]);
      }
    };

    void loadCategories();
  }, []);

  return (
    <div className="pt-32 pb-24">
      <div className="container mx-auto px-4">
        <div className="mb-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-white/70 px-4 py-2 backdrop-blur-sm">
            <Link
              to="/"
              className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground transition-colors hover:text-primary"
            >
              Home
            </Link>
            <span className="h-1 w-1 rounded-full bg-border" />
            <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-foreground">Our Story</span>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
            <div className="rounded-[2rem] border border-border bg-white/85 p-6 md:p-8 backdrop-blur-sm">
              <p className="text-sm font-semibold uppercase tracking-[0.28em] text-primary">Our Story</p>
              <h1 className="mt-4 text-4xl font-bold tracking-tight text-foreground md:text-5xl">Hi, I&apos;m Anindita</h1>
              <p className="mt-5 text-base leading-8 text-muted-foreground md:text-lg">
                Aurora Blings is not just a jewelry brand. It&apos;s a dream I paused, but never gave up on.
              </p>
              <p className={bodyTextClass}>
                I first started this journey in 2020, but life had other plans. I moved to the US, things changed, and I
                had to put my brand on hold.
              </p>
              <p className={bodyTextClass}>
                But somewhere deep down, I always knew this was just a pause, not the end.
              </p>
              <p className={bodyTextClass}>
                This time, I&apos;m not building it alone. My husband, who is also my co-founder, has been a constant support,
                handling everything behind the scenes while I bring the creative side to life.
              </p>
              <p className={bodyTextClass}>
                Aurora Blings is our way of starting again, building something with love, intention, and courage.
              </p>
              <p className={bodyTextClass}>
                Every piece you see here is carefully chosen to make you feel confident, elegant, and a little more you.
              </p>
            </div>

            <div className="rounded-[2rem] border border-border bg-[#f5f8f2] p-6 md:p-8">
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-primary">What Guides Us</p>
              <div className="mt-5 space-y-5">
                <div>
                  <h2 className="text-lg font-semibold text-foreground">Curated with intention</h2>
                  <p className="mt-2 text-sm leading-7 text-muted-foreground">
                    Stylish, affordable pieces chosen for everyday elegance and modern charm.
                  </p>
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-foreground">Transparent always</h2>
                  <p className="mt-2 text-sm leading-7 text-muted-foreground">
                    We offer fashion and imitation jewelry only, never real gold, silver, or precious metals.
                  </p>
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-foreground">Built with care</h2>
                  <p className="mt-2 text-sm leading-7 text-muted-foreground">
                    Every order supports a business being rebuilt with honesty, courage, and heart.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <section className="rounded-3xl border border-border bg-white/85 p-6 md:p-10 backdrop-blur-sm">
            <h2 className={sectionTitleClass}>About Aurora Blings</h2>
            <p className={bodyTextClass}>
              Aurora Blings was conceptualized by Anindita and is operated as a proprietorship business owned by Bimba Dhar Dash.
            </p>
            <p className={bodyTextClass}>
              This structure allows us to combine creativity and business strength, where one brings the vision and the other
              ensures everything runs smoothly behind the scenes.
            </p>
          </section>

          <section className="rounded-3xl border border-border bg-white/85 p-6 md:p-10 backdrop-blur-sm">
            <h2 className={sectionTitleClass}>What We Offer</h2>
            <p className={bodyTextClass}>
              At Aurora Blings, we curate stylish and affordable pieces designed for everyday elegance.
            </p>
            {activeCategories.length > 0 ? (
              <ul className={listClass}>
                {activeCategories.map((categoryName) => (
                  <li key={categoryName}>{categoryName}</li>
                ))}
              </ul>
            ) : null}
            <p className={bodyTextClass}>
              Each piece is selected to reflect modern trends while maintaining timeless charm.
            </p>
          </section>

          <section className="rounded-3xl border border-border bg-white/85 p-6 md:p-10 backdrop-blur-sm">
            <h2 className={sectionTitleClass}>Product Transparency</h2>
            <p className={bodyTextClass}>
              Aurora Blings offers fashion and imitation jewelry.
            </p>
            <p className={bodyTextClass}>
              We do not deal in real gold, silver, or precious metals. All products are made using artificial materials and
              are intended for fashion purposes only.
            </p>
          </section>

          <section className="rounded-3xl border border-border bg-white/85 p-6 md:p-10 backdrop-blur-sm">
            <h2 className={sectionTitleClass}>Our Promise</h2>
            <ul className={listClass}>
              <li>Delivering quality products at fair prices</li>
              <li>Maintaining complete transparency</li>
              <li>Providing secure and reliable shopping experiences</li>
              <li>Offering responsive customer support</li>
            </ul>
          </section>

          <section className="rounded-3xl border border-border bg-[#eef4e7] p-6 md:p-10">
            <h2 className={sectionTitleClass}>Thank You</h2>
            <p className={bodyTextClass}>
              Thank you for being a part of this journey.
            </p>
            <p className={bodyTextClass}>
              Every order you place supports a dream that refused to give up. This is just the beginning.
            </p>
            <div className="mt-6">
              <Link
                to="/contact-us/"
                className="inline-flex items-center rounded-full bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Contact Us
              </Link>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};
