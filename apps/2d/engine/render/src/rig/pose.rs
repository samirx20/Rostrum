//! A rig's bones at time t (RIG.md › Evaluation 1–3): rest frames, FK (parents before children), then the IK
//! chains (ik.rs), and each bone's delta from rest. A pure function of the rig and t: no state between frames.

use serde_json::{Map, Value};

use super::ik::{self, IkOut};
use super::math::{Aff, Pt};
use crate::scene::eval::props_at;
use crate::scene::Node;

pub struct Pose {
    pub ids: Vec<String>,
    pub parent: Vec<Option<usize>>,
    /// Rest length, px (the posed one is this times the frame's scale).
    pub length: Vec<f64>,
    /// Rest frame: T(x, y) · Rot(angle), rig px.
    pub rest: Vec<Aff>,
    /// Posed frame, rig px.
    pub world: Vec<Aff>,
    pub iks: Vec<IkOut>,
}

pub(super) fn num(p: &Map<String, Value>, f: &str) -> f64 {
    p.get(f).and_then(Value::as_f64).unwrap_or(0.0)
}

pub(super) fn text<'a>(p: &'a Map<String, Value>, f: &str) -> &'a str {
    p.get(f).and_then(Value::as_str).unwrap_or("")
}

impl Pose {
    /// The rig node's bones posed at `t` (its parts were checked when the scene loaded: check.rs).
    pub fn solve(rig: &Node, t: f64) -> Pose {
        let bones: Vec<&Node> = rig.rig.iter().filter(|p| p.kind == "bone").collect();
        let props: Vec<Map<String, Value>> = bones.iter().map(|b| props_at(b, t).into_owned()).collect();
        let ids: Vec<String> = bones.iter().map(|b| b.id.clone()).collect();
        let parent: Vec<Option<usize>> = props.iter().map(|p| ids.iter().position(|id| id == text(p, "parent"))).collect();
        let rest: Vec<Aff> = props.iter().map(|p| Aff::translate(num(p, "x"), num(p, "y")) * Aff::rotate(num(p, "angle"))).collect();
        let n = ids.len();
        let mut pose = Pose {
            length: props.iter().map(|p| num(p, "length")).collect(),
            world: vec![Aff::ID; n],
            iks: vec![],
            ids, parent, rest,
        };
        for i in pose.order() {
            let p = &props[i];
            let (parent_world, parent_rest) = pose.parent[i].map_or((Aff::ID, Aff::ID), |q| (pose.world[q], pose.rest[q]));
            let local = parent_rest.inverse().expect("a rest frame is a move and a turn") * pose.rest[i];
            let s = num(p, "scale");
            pose.world[i] = parent_world * Aff::translate(num(p, "moveX"), num(p, "moveY")) * local * Aff::rotate(num(p, "rotation")) * Aff::scale(s, s);
        }
        ik::apply(&mut pose, rig, t);
        pose
    }

    pub fn index(&self, id: &str) -> Option<usize> {
        self.ids.iter().position(|b| b == id)
    }

    /// How deep a bone sits (a root is 0).
    pub fn depth(&self, i: usize) -> usize {
        let (mut d, mut cur) = (0, self.parent[i]);
        while let Some(p) = cur {
            d += 1;
            cur = if d > self.ids.len() { None } else { self.parent[p] };
        }
        d
    }

    /// Bones parents first (stable, by depth).
    fn order(&self) -> Vec<usize> {
        let mut order: Vec<usize> = (0..self.ids.len()).collect();
        order.sort_by_key(|&i| self.depth(i));
        order
    }

    /// Whether `i` is `root` or below it.
    fn under(&self, mut i: usize, root: usize) -> bool {
        for _ in 0..=self.ids.len() {
            if i == root {
                return true;
            }
            match self.parent[i] {
                Some(p) => i = p,
                None => return false,
            }
        }
        false
    }

    /// Turns a bone and everything below it by `deg` about the point `p` (rig px).
    pub fn turn_from(&mut self, root: usize, deg: f64, p: Pt) {
        let r = Aff::rotate_about(deg, p);
        for i in 0..self.ids.len() {
            if self.under(i, root) {
                self.world[i] = r * self.world[i];
            }
        }
    }

    pub fn pivot(&self, i: usize) -> Pt {
        self.world[i].origin()
    }

    pub fn tip(&self, i: usize) -> Pt {
        self.world[i].apply((self.length[i], 0.0))
    }

    /// D_b = P_b · R_b⁻¹: the bone's move, turn and scale from rest, rig px.
    pub fn delta(&self, i: usize) -> Aff {
        self.world[i] * self.rest[i].inverse().expect("a rest frame is a move and a turn")
    }
}
