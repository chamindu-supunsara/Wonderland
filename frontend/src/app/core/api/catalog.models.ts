export interface Attraction {
  id: string;
  name: string;
  description: string;
  category: string;
  thrill_level: string;
  min_age: number | null;
  min_height_cm: number | null;
  guidance_text: string;
}

export interface TicketTier {
  id: string;
  code: string;
  name: string;
  min_guests: number;
  max_guests: number;
  amount_minor: number;
  currency: string;
  price_version: number;
}
