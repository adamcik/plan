/* This file is part of the plan timetable generator, see LICENSE for details. */

(function () {
  const zigZagDecode = (i) => (i >> 1) ^ -(i & 1);

  class DeltaDeltaDecoder {
    constructor() {
      this.prev = null;
      this.prev_delta = 0;
    }
    decode(value) {
      if (this.prev === null) {
        this.prev = value;
        return value;
      }
      this.prev_delta += value;
      this.prev += this.prev_delta;
      return this.prev;
    }
  }

  window.drawCalendar = (container, url) => {
    // FIXME: Consider show active dates for new semesters?
    fetch(url)
      .then((response) => response.text())
      .then((content) => {
        const data = [];

        const daysDecoder = new DeltaDeltaDecoder();
        const countsDecoder = new DeltaDeltaDecoder();

        content.split(",").forEach((v) => {
          v = v.split(":");
          v = v.length == 1 ? [0, v[0]] : v;
          v = v.map((i) => zigZagDecode(Number(i)));
          data.push({
            date: new Date(8.64e7 * daysDecoder.decode(v[0])),
            value: countsDecoder.decode(v[1]),
          });
        });
        return data;
      })
      .then((data) => {
        const start = d3.utcDay.offset(d3.min(data, (d) => d.date));
        const end = d3.utcDay.offset(d3.max(data, (d) => d.date));

        const iso_year = (d) => Number(d3.timeFormat("%G")(d));
        const iso_week = (d) => Number(d3.timeFormat("%V")(d));
        const iso_dow = (d) => Number(d3.timeFormat("%u")(d));

        function calendar({
          date = Plot.identity,
          inset = 0.5,
          ...options
        } = {}) {
          let D;
          return {
            fy: {
              transform: (data) =>
                (D = Plot.valueof(data, date, Array)).map((d) => iso_year(d)),
            },
            x: {
              transform: () => D.map((d) => iso_week(d) - 1),
            },
            y: { transform: () => D.map((d) => iso_dow(d)) },
            inset,
            ...options,
          };
        }

        class MonthLine extends Plot.Mark {
          static defaults = { stroke: "currentColor", strokeWidth: 1 };
          constructor(data, options = {}) {
            const { x, y } = options;
            super(
              data,
              { x: { value: x, scale: "x" }, y: { value: y, scale: "y" } },
              options,
              MonthLine.defaults,
            );
          }
          render(index, { x, y }, { x: X, y: Y }, dimensions) {
            const { marginTop, marginBottom, height } = dimensions;
            const dx = x.bandwidth(),
              dy = y.bandwidth();
            return htl.svg`<path fill=none stroke=${this.stroke} stroke-width=${this.strokeWidth} d=${Array.from(
              index,
              (i) =>
                `${
                  Y[i] > marginTop + dy * 1.5 // is the first day a Monday?
                    ? `M${X[i] + dx},${marginTop + dy}V${Y[i]}h${-dx}`
                    : `M${X[i]},${marginTop + dy}`
                }V${height - marginBottom}`,
            ).join("")}>`;
          }
        }

        return Plot.plot({
          padding: 0,
          width: 920,
          height: d3.utcYear.count(start, end) * 100,
          //marginLeft: 10,
          x: {
            axis: null,
            domain: d3.range(53),
          },
          y: {
            axis: "left",
            tickFormat: Plot.formatWeekday("en"),
            tickSize: 0,
            domain: [-1, 1, 2, 3, 4, 5, 6, 7],
            ticks: [1, 2, 3, 4, 5, 6, 7],
          },
          fy: {
            tickFormat: "",
            reverse: true,
          },
          color: {
            // FIXME: Tweak scale
            scheme: "Greens",
            type: "pow",
            exponent: 1 / 5,
          },
          marks: [
            Plot.cell(
              data,
              calendar({
                date: "date",
                fill: (d) => d.value,
                title: (d) =>
                  `${d3.utcFormat("%Y-%m-%d")(d.date)}\n${d.value} new timetables`,
              }),
            ),
            new MonthLine(
              d3.utcMonths(d3.utcMonth(start), end),
              calendar({ stroke: "white", strokeWidth: 3 }),
            ),
            Plot.text(
              d3.utcMonths(d3.utcMonth(start), end).map(d3.utcThursday.ceil),
              calendar({
                text: d3.utcFormat("%b"),
                frameAnchor: "left",
                y: -1,
                dx: -5,
              }),
            ),
            Plot.text(
              // Group by last sunday of the month, i.e. get next month and go one day back, then find sunday.
              [
                ...d3.rollup(
                  data,
                  (v) => d3.sum(v, (d) => d.value),
                  (d) =>
                    d3.utcThursday.floor(
                      d3.utcDay.offset(d3.utcMonth.ceil(d.date), -1),
                    ),
                ),
              ].map(([date, value]) => ({ date, value })),
              calendar({
                date: "date",
                text: (d) => d.value,
                frameAnchor: "right",
                y: -1,
                dx: 5,
              }),
            ),
            //Plot.text(
            //  d3.utcDays(start, end),
            //  calendar({ text: d3.utcFormat("%-d") }),
            //),
          ],
        });
      })
      .then((plot) => {
        container.appendChild(plot);
      });
  };
})();
