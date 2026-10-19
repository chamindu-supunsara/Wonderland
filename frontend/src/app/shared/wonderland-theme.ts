import { definePreset } from '@primeuix/themes';
import AuraBase from '@primeuix/themes/aura/base';
import ButtonTheme from '@primeuix/themes/aura/button';
import InputTextTheme from '@primeuix/themes/aura/inputtext';
import TextareaTheme from '@primeuix/themes/aura/textarea';
import TagTheme from '@primeuix/themes/aura/tag';
import SkeletonTheme from '@primeuix/themes/aura/skeleton';

// Include only the component tokens used by this application.
export const WonderlandTheme = definePreset(
  {
    ...AuraBase,
    components: {
      button: ButtonTheme,
      inputtext: InputTextTheme,
      textarea: TextareaTheme,
      tag: TagTheme,
      skeleton: SkeletonTheme,
    },
  },
  {
    semantic: {
      primary: {
        50: '#eef8f3',
        100: '#d5ecdf',
        200: '#add8bf',
        300: '#7bbd9a',
        400: '#4c9b76',
        500: '#287c59',
        600: '#1b6347',
        700: '#174f3b',
        800: '#163f31',
        900: '#12372b',
        950: '#092219',
      },
      focusRing: { width: '3px', style: 'solid', color: '#9ecbb6', offset: '3px' },
      formField: { borderRadius: '10px', paddingX: '1rem', paddingY: '0.8rem' },
    },
    components: {
      button: { root: { borderRadius: '10px', paddingX: '1.15rem', paddingY: '0.8rem' } },
      tag: { root: { borderRadius: '7px', padding: '0.35rem 0.65rem' } },
    },
  },
);
