import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { AuthService } from './core/auth/auth-service';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App { readonly auth = inject(AuthService); }
