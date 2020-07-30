def save_generic_constraints(self, m):
    """Save generic constraints for later inspection"""

    with open(os.path.join(self.output_dir, 'constraints.txt'), 'w') as f:
        for k, v in m.C_GENERIC_CONSTRAINT.items():
            to_write = f"{k}: {v.expr}\n"
            f.write(to_write)
