"use client";

interface Props {
  data: number[];
  width?: number;
  height?: number;
}

export default function Sparkline({ data, width = 80, height = 24 }: Props) {
  if (data.length < 2) {
    return <svg width={width} height={height} className="opacity-30" />;
  }
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const stepX = width / (data.length - 1);
  const points = data
    .map((v, i) => {
      const x = i * stepX;
      const y = height - ((v - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const rising = data[data.length - 1] >= data[0];
  const color = rising ? "#16c784" : "#ea3943";

  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
