import type {
  ForwardRefExoticComponent,
  PropsWithoutRef,
  RefAttributes,
  SVGProps,
} from "react";
import {
  AdjustmentsHorizontalIcon,
  ArrowDownRightIcon,
  ArrowPathIcon,
  ArrowRightIcon,
  ArrowTopRightOnSquareIcon,
  ArrowUpIcon,
  ArrowUpRightIcon,
  Bars3Icon,
  BookOpenIcon,
  ChatBubbleLeftRightIcon,
  CheckIcon,
  ChevronDownIcon,
  EyeIcon,
  InformationCircleIcon,
  MagnifyingGlassIcon,
  MinusIcon,
  PlusIcon,
  RectangleStackIcon,
  ScaleIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";

type HeroIcon = ForwardRefExoticComponent<
  PropsWithoutRef<
    SVGProps<SVGSVGElement> & { title?: string; titleId?: string }
  > &
    RefAttributes<SVGSVGElement>
>;
type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function sized(Icon: HeroIcon) {
  return function SizedHeroIcon({ size = 16, ...props }: IconProps) {
    return <Icon width={size} height={size} {...props} />;
  };
}

export const AdjustmentsHorizontal = sized(AdjustmentsHorizontalIcon);
export const ArrowDownRight = sized(ArrowDownRightIcon);
export const ArrowPath = sized(ArrowPathIcon);
export const ArrowRight = sized(ArrowRightIcon);
export const ArrowTopRightOnSquare = sized(ArrowTopRightOnSquareIcon);
export const ArrowUp = sized(ArrowUpIcon);
export const ArrowUpRight = sized(ArrowUpRightIcon);
export const Bars3 = sized(Bars3Icon);
export const BookOpen = sized(BookOpenIcon);
export const ChatBubbleLeftRight = sized(ChatBubbleLeftRightIcon);
export const Check = sized(CheckIcon);
export const ChevronDown = sized(ChevronDownIcon);
export const Eye = sized(EyeIcon);
export const InformationCircle = sized(InformationCircleIcon);
export const MagnifyingGlass = sized(MagnifyingGlassIcon);
export const Minus = sized(MinusIcon);
export const Plus = sized(PlusIcon);
export const RectangleStack = sized(RectangleStackIcon);
export const Scale = sized(ScaleIcon);
export const XMark = sized(XMarkIcon);
