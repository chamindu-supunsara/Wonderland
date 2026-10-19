import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-not-found-page',
  imports: [RouterLink],
  template: `<div class="page-container">
    <h1>That adventure isn't here.</h1>
    <p>Let's find your way back to the park.</p>
    <a class="button" routerLink="/">Explore Wonderland</a>
  </div>`,
})
export class NotFoundPage {}
