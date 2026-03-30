import React, { useState } from 'react';
import type { FormEvent } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import contactService from '@/services/api/contact';
import { Button } from '@/components/ui/Button';
import { useTurnstileConfig } from '@/hooks/useTurnstileConfig';
import { TurnstileWidget } from '@/components/security/TurnstileWidget';

interface ContactFormState {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  subject: string;
  message: string;
}

const initialState: ContactFormState = {
  firstName: '',
  lastName: '',
  email: '',
  phone: '',
  subject: '',
  message: '',
};

export const ContactUsPage: React.FC = () => {
  const [form, setForm] = useState<ContactFormState>(initialState);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [turnstileToken, setTurnstileToken] = useState('');
  const [turnstileResetKey, setTurnstileResetKey] = useState(0);
  const { turnstileEnabled, turnstileSiteKey } = useTurnstileConfig();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');
    if (turnstileEnabled && !turnstileToken) {
      setErrorMessage('Please complete CAPTCHA verification.');
      return;
    }
    setIsSubmitting(true);

    try {
      const fullName = `${form.firstName} ${form.lastName}`.trim();
      const response = await contactService.submitQuery({
        name: fullName,
        email: form.email.trim(),
        phone: form.phone.trim(),
        subject: form.subject.trim(),
        message: form.message.trim(),
        turnstile_token: turnstileToken,
      });

      setSuccessMessage(response?.message || 'Thanks for reaching out. Our team will contact you soon.');
      setForm(initialState);
      setTurnstileToken('');
      setTurnstileResetKey((prev) => prev + 1);
    } catch (error: unknown) {
      setTurnstileToken('');
      setTurnstileResetKey((prev) => prev + 1);
      if (axios.isAxiosError(error)) {
        const apiMessage = (error.response?.data as { message?: string } | undefined)?.message;
        setErrorMessage(apiMessage || 'Unable to submit your query right now. Please try again.');
      } else if (error instanceof Error) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage('Unable to submit your query right now. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="pt-32 pb-24">
      <div className="container mx-auto px-4">
        <div className="mb-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-white/70 backdrop-blur-sm px-4 py-2">
            <Link to="/" className="text-[10px] uppercase tracking-[0.18em] font-semibold text-muted-foreground hover:text-primary transition-colors">
              Home
            </Link>
            <span className="h-1 w-1 rounded-full bg-border" />
            <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-foreground">Contact Us</span>
          </div>
          <h1 className="mt-4 text-4xl md:text-5xl font-bold tracking-tight text-foreground">Get In Touch</h1>
          <p className="mt-3 text-muted-foreground max-w-2xl">
            Please select a topic related to your inquiry. If you need support, fill out the form and our team will get back shortly.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="rounded-3xl border border-border bg-white/85 backdrop-blur-sm p-6 md:p-8">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <input
                  type="text"
                  placeholder="Enter Your First Name"
                  value={form.firstName}
                  onChange={(e) => setForm((prev) => ({ ...prev, firstName: e.target.value }))}
                  className="w-full h-12 rounded-xl border border-border px-4 text-sm"
                  required
                />
                <input
                  type="text"
                  placeholder="Enter Your Last Name"
                  value={form.lastName}
                  onChange={(e) => setForm((prev) => ({ ...prev, lastName: e.target.value }))}
                  className="w-full h-12 rounded-xl border border-border px-4 text-sm"
                  required
                />
              </div>

              <input
                type="email"
                placeholder="Enter Your Email"
                value={form.email}
                onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))}
                className="w-full h-12 rounded-xl border border-border px-4 text-sm"
                required
              />

              <input
                type="text"
                placeholder="Enter Your Phone Number"
                value={form.phone}
                onChange={(e) => setForm((prev) => ({ ...prev, phone: e.target.value }))}
                className="w-full h-12 rounded-xl border border-border px-4 text-sm"
              />

              <input
                type="text"
                placeholder="Subject (optional)"
                value={form.subject}
                onChange={(e) => setForm((prev) => ({ ...prev, subject: e.target.value }))}
                className="w-full h-12 rounded-xl border border-border px-4 text-sm"
              />

              <textarea
                placeholder="Please leave your comments here..."
                value={form.message}
                onChange={(e) => setForm((prev) => ({ ...prev, message: e.target.value }))}
                className="w-full min-h-[150px] rounded-xl border border-border px-4 py-3 text-sm resize-none"
                required
              />

              {errorMessage ? <p className="text-sm text-red-600">{errorMessage}</p> : null}
              {successMessage ? <p className="text-sm text-green-700">{successMessage}</p> : null}
              <TurnstileWidget
                enabled={turnstileEnabled}
                siteKey={turnstileSiteKey}
                resetKey={turnstileResetKey}
                onTokenChange={setTurnstileToken}
              />

              <Button
                type="submit"
                disabled={isSubmitting}
                className="h-11 rounded-xl px-6 bg-primary text-primary-foreground hover:bg-primary/90"
              >
                {isSubmitting ? 'Submitting...' : 'Submit'}
              </Button>
            </form>
          </div>

          <div className="rounded-3xl overflow-hidden border border-border bg-white/85 backdrop-blur-sm min-h-[560px]">
            <iframe
              title="Aurora Blings Location"
              src="https://www.google.com/maps?q=Gangamata+Bagicha,+Near+Nabakalebara+Road,+Puri+752002&output=embed"
              className="w-full h-full min-h-[560px]"
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
            />
          </div>
        </div>
      </div>
    </div>
  );
};
