/** An ink illustration extending the app's existing rounded panda identity. */
export function LandingPanda() {
  return (
    <svg
      viewBox="0 0 500 530"
      role="img"
      aria-label="Pandaset panda mascot"
      className="landing-panda"
    >
      <ellipse
        cx="257"
        cy="491"
        rx="139"
        ry="14"
        fill="#151515"
        opacity=".09"
      />
      <path
        d="M152 313c-35 42-48 117-23 151 36 38 208 40 248-3 19-30 5-114-30-148Z"
        fill="#171717"
      />
      <ellipse cx="252" cy="387" rx="87" ry="93" fill="#fff" />
      <path
        d="M190 464c-13-34-54-42-75-17-26 31-22 57 16 62 38 7 62-10 59-45m131 0c12-34 53-42 74-17 26 31 22 57-16 62-38 7-61-10-58-45"
        fill="#151515"
      />
      <path
        d="M142 337c-46-16-63 35-53 77 6 28 29 44 49 29 19-14 12-36 25-55"
        fill="#151515"
      />
      <path
        className="lp-panda-wave-paw"
        d="M345 337c45-16 64 35 53 77-6 28-29 44-49 29-19-14-12-36-25-55"
        fill="#151515"
      />
      <g className="lp-panda-head">
        <circle cx="133" cy="147" r="54" fill="#151515" />
        <circle cx="369" cy="147" r="54" fill="#151515" />
        <path
          d="M251 126c-86-1-143 62-148 136-6 70 52 110 148 111 95 0 155-41 148-111-6-74-62-137-148-136Z"
          fill="#fff"
          stroke="#151515"
          strokeWidth="3"
        />
        <path
          d="M220 134c15-10 37-11 53-6l-9 8 13 3"
          fill="#fff"
          stroke="#151515"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <ellipse
          cx="190"
          cy="249"
          rx="35"
          ry="46"
          transform="rotate(27 190 249)"
          fill="#151515"
        />
        <ellipse
          cx="312"
          cy="249"
          rx="35"
          ry="46"
          transform="rotate(-27 312 249)"
          fill="#151515"
        />
        <g className="lp-panda-gaze">
          <g className="lp-panda-blink">
            <ellipse cx="201" cy="246" rx="9" ry="12" fill="#fff" />
            <ellipse cx="301" cy="246" rx="9" ry="12" fill="#fff" />
            <circle cx="204" cy="249" r="4.5" fill="#151515" />
            <circle cx="298" cy="249" r="4.5" fill="#151515" />
          </g>
        </g>
        <path
          d="M236 290c0-9 31-9 31 0 0 8-8 13-16 13s-15-5-15-13Z"
          fill="#151515"
        />
        <path
          d="M251 303v10m0 0c-10 11-21 11-28 1m28-1c10 11 21 11 28 1"
          fill="none"
          stroke="#151515"
          strokeWidth="3.5"
          strokeLinecap="round"
        />
        <path
          d="m144 288 17 4m-17 3 14 3m183-6 17-4m-14 10 14-3"
          stroke="#bcbcbc"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </g>
    </svg>
  );
}
