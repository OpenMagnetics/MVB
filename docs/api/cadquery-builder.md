# CadQuery Builder

The CadQuery rendering engine. Contains all shape classes, bobbin/winding builders, and export logic.

## Module Overview

::: OpenMagneticsVirtualBuilder.cadquery_builder
    options:
      show_source: false
      members: false

## Main Builder Class

::: OpenMagneticsVirtualBuilder.cadquery_builder.CadQueryBuilder
    options:
      show_source: false
      members_order: source
      heading_level: 3
      filters:
        - "!^_"
        - "!^IPiece"
        - "!^P$"
        - "!^E$"
        - "!^U$"

## Enums

::: OpenMagneticsVirtualBuilder.cadquery_builder.WireType
    options:
      show_source: false
      heading_level: 3

::: OpenMagneticsVirtualBuilder.cadquery_builder.ColumnShape
    options:
      show_source: false
      heading_level: 3

## Data Classes

::: OpenMagneticsVirtualBuilder.cadquery_builder.WireDescription
    options:
      show_source: false
      heading_level: 3

::: OpenMagneticsVirtualBuilder.cadquery_builder.TurnDescription
    options:
      show_source: false
      heading_level: 3

::: OpenMagneticsVirtualBuilder.cadquery_builder.BobbinProcessedDescription
    options:
      show_source: false
      heading_level: 3

## Utility Functions

::: OpenMagneticsVirtualBuilder.cadquery_builder.set_tessellation_quality
    options:
      show_source: true
      heading_level: 3

::: OpenMagneticsVirtualBuilder.cadquery_builder.resolve_dimensional_value
    options:
      show_source: true
      heading_level: 3
